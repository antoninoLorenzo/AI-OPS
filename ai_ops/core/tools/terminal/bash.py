import re
import os
import pty
import fcntl
import struct
import signal
import select
import termios
import subprocess
import logging
import uuid
import time
from dataclasses import dataclass

_logger = logging.getLogger(__name__)

ANSI_RE = re.compile(r'\x1B[@-_][0-?]*[ -/]*[@-~]')


def strip_ansi(s: str) -> str:
    return ANSI_RE.sub('', s)


def _setup_subprocess(fd, ps1):
    # note: preexec_fn takes no args so return a closure.
    # note: setup subprocess is put there so it can be changed if testing required
    def inner():
        os.setsid()                               # set slave as session owner
        fcntl.ioctl(fd, termios.TIOCSCTTY, 0)     # set slave as controlling terminal
        # substitutes "$" with custom sentinel (only for non interactive commands)
        os.environ['PS1'] = ps1                        
    return inner



CommandStatus = {
    0: 'ok',
    2: 'misuse of shell builtins',
    126: 'missing execute permission',
    127: 'command not found',
}

COMMAND_TIMEOUT_MESSAGE = "Command killed for timeout"


@dataclass
class CommandOutput:
    output: str
    status: str


class BashSession:

    def __init__(self, read_timeout: int = 30):
        self.process = None
        # R/W file descriptors, subprocess uses slave, parent uses master
        self.master_fd = None
        self.slave_fd = None
        # when an interactive command is executed the subsequent ones are 
        # marked as interactive by default, reset when write_sentinel is 
        # seen for the first time in the output.
        self.is_interactive = False
        # write sentinel is used to determine end of command execution for 
        # non-interactive commands.
        self.write_sentinel = f'__{str(uuid.uuid4())[:13]}_READY__'
        self.command_to_signal = { 'Ctrl+C': signal.SIGINT }
        self.read_timeout = read_timeout

        self.__start_session()
    
    def run(self, command: str, interactive: bool = False) -> CommandOutput:
        if not isinstance(command, str) or len(command) == 0:
            raise ValueError('Empty command in BashSession.run')
        
        # execute
        if command in self.command_to_signal:
            self.__send_signal(self.command_to_signal[command])
            _logger.info("executed __send_signal", command=command)
        else:
            self.__send_command(command)
            _logger.info("executed __send_command", command=command)
        
        # fetch output
        if interactive or self.is_interactive:
            self.is_interactive = True
            _logger.info('starting read in interactive mode')
            return CommandOutput(output=self.__read_interactive(), status='unknown')
        else:
            _logger.info('starting read in default mode')
            command_output = self.__read()

            # capture status of last executed command (useful for heuristics)
            self.__send_command("printf '%d\n' $?")
            status = self.__read()
            status_code = 0
            _logger.debug('acquired status code', status=status)
            
            try:
                status_code = int(status.lstrip(' > ').strip())
            except ValueError:
                pass

            return CommandOutput(output=command_output, status=status_code)
            
    def close(self):
        os.close(self.master_fd)
        self.process.terminate()

    def __start_session(self):
        self.master_fd, self.slave_fd = pty.openpty()

        # disable ECHO on slave
        slave_attrs_bkup = termios.tcgetattr(self.slave_fd) 
        slave_attrs = list(slave_attrs_bkup)
        slave_attrs[3] = slave_attrs[3] & ~termios.ECHO  # pos 3 is lflag, unset ECHO 
        termios.tcsetattr(self.slave_fd, termios.TCSANOW, slave_attrs)

        # starts a shell session with `/bin/sh -i` whether the command is interactive 
        # (ex. ssh) or not (ex. ls); `/bin/bash` is less reliable on output (thx ANSI).
        # note: just using `shell=True` makes the subprocess close after executing non
        # interactive commands (ex. ls). 
        self.process = subprocess.Popen(
            ['/bin/sh', '-i'], # commands[0],
            stdin=self.slave_fd,
            stdout=self.slave_fd,
            stderr=self.slave_fd,
            preexec_fn=_setup_subprocess(fd=self.slave_fd, ps1=self.write_sentinel)
        )
        os.close(self.slave_fd)  # owning process doesn't need the slave

        # check if terminal ready 
        self.__read()
        time.sleep(0.5)

    def __send_command(self, command: str):
        cmd_bytes = (command + '\n').encode()
        if os.write(self.master_fd, cmd_bytes) != len(cmd_bytes):
            _logger.error("command partially sent")

    def __send_signal(self, signal):
        # signal the foreground process
        # TIOCGPGRP is used to get the process id of the foreground process (see 1);
        # the call to ioctl with TIOCGPGRP requires a pid_t as argp, so use 'i' that
        # is an integer of 4 bytes.
        # 1: https://man7.org/linux/man-pages/man2/TIOCGPGRP.2const.html
        # 2: https://docs.python.org/3/library/struct.html#format-characters
        argp = struct.pack('i', 0)
        foreground_pid_bytes = fcntl.ioctl(self.master_fd, termios.TIOCGPGRP, argp)
        foreground_pid = struct.unpack('i', foreground_pid_bytes)[0] # unpack returns a tuple
        os.killpg(foreground_pid, signal)

    def __read(self) -> str:
        # use select to implement timeout mechanism
        poller = select.poll()
        poller.register(self.master_fd, select.POLLIN | select.POLLPRI)

        cmd_output = ''
        start = time.time()
        while True: 
            time.sleep(0.1)
            events = poller.poll(0)
            for fd, _ in events:
                if fd != self.master_fd:
                    continue

                cmd_output += strip_ansi(
                    os.read(self.master_fd, 4096).decode('utf-8', errors='replace')
                )
            
            # exit on sentinel
            if self.write_sentinel in cmd_output:
                cmd_output = cmd_output.replace(self.write_sentinel, '')
                break

            # or exit on timeout
            elapsed = time.time() - start
            if elapsed >= self.read_timeout:
                cmd_output += COMMAND_TIMEOUT_MESSAGE + f'({self.read_timeout})s\n'
                self.__send_signal(signal.SIGKILL)
                time.sleep(0.1)
                break
        return cmd_output

    def __read_interactive(self) -> str:
        poller = select.poll()
        poller.register(self.master_fd, select.POLLIN | select.POLLPRI)
        
        cmd_output = ''
        base_delay = 0.2
        max_delay = 12
        consecutive_empty = 0
        while True:
            time.sleep(base_delay)
            events = poller.poll(0)
            for fd, _ in events:
                # read if any 
                if fd != self.master_fd:
                    continue
                cmd_output += strip_ansi(
                    os.read(self.master_fd, 4096).decode('utf-8', errors='replace')
                )
                consecutive_empty = 0 # reset if new output

            # exponential backoff 
            base_delay = base_delay * 2
            if base_delay >= max_delay:
                _logger.debug("max delay reached in interactive read")
                break
            if len(cmd_output) > 0:
                consecutive_empty += 1
                if consecutive_empty >= 2:
                    _logger.debug("done reading in interactive read")
                    break

        if self.write_sentinel in cmd_output:
            cmd_output = cmd_output.replace(self.write_sentinel, '')
            self.is_interactive = False
        return cmd_output  

