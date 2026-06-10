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
import enum
from dataclasses import dataclass
from typing import Tuple, Dict

from ai_ops.core.log import get_logger, log_event, logging

_logger = get_logger(__name__)

ANSI_RE = re.compile(r'\x1B[@-_][0-?]*[ -/]*[@-~]')


def strip_ansi(s: str) -> str:
    return ANSI_RE.sub('', s)


def _setup_subprocess(fd, ps1):
    # passed to Popen preexec_fn to setup the bash process, since preexec_fn takes no 
    # args returns a closure.
    def inner():
        os.setsid()                               # set slave as session owner
        fcntl.ioctl(fd, termios.TIOCSCTTY, 0)     # set slave as controlling terminal
        os.environ['PS1'] = ps1                        
    return inner

# shell-reserved exit codes: https://tldp.org/LDP/abs/html/exitcodes.html
# signals 128+n: https://man7.org/linux/man-pages/man7/signal.7.html
class CommandStatus(enum.Enum):
    UNKNOWN = -1
    OK = 0
    ERR_GENERAL = 1
    ERR_BUILTIN = 2
    NOT_EXECUTABLE = 126
    NOT_FOUND = 127
    SIGINT = 130
    KILLED = 137

Status2String: Dict[CommandStatus, str] = {
    CommandStatus.UNKNOWN: 'unknown status',
    CommandStatus.OK: "Successful termination",
    CommandStatus.ERR_GENERAL: 'unknown error',
    CommandStatus.ERR_BUILTIN: "Misuse of shell builtins",
    CommandStatus.NOT_EXECUTABLE: "Permission problem or command is not an executable",
    CommandStatus.NOT_FOUND: 'command not found',
    CommandStatus.KILLED: 'killed'
}

String2Signal = {
   'Ctrl+C': signal.SIGINT 
}


@dataclass
class CommandOutput:
    output: str
    status: CommandStatus
    timed_out: bool = False


class BashSession:

    def __init__(self, default_timeout: float = 30.0):
        self.default_timeout = default_timeout

        # The implementation spawns `/bin/sh` in a subprocess and uses R/W 
        # fds to interact with it.
        self.process = None
        self.master_fd = None
        self.slave_fd = None
        
        # when an interactive command is executed the subsequent ones are 
        # marked as interactive by default, reset when write_sentinel is 
        # seen for the first time in the output.
        self.is_interactive = False
        
        # write sentinel is used to determine end of command execution for 
        # non-interactive commands.
        self.write_sentinel = f'__{str(uuid.uuid4())[:13]}_READY__'
        self.__status_pattern = re.compile(r"> (\d+)", re.MULTILINE)

        self.__start_session()
    
    def run(
        self, 
        command: str, 
        timeout: float = None,
        interactive: bool = False
    ) -> CommandOutput:
        """By default executes a command in non-interactive mode, meaning that only commands that 
        do not require interaction can be executed (think ls). 

        When a command exceeds the timeout it gets killed (SIGKILL) to avoid interfering with 
        successive commands. 
        """
        log_event(
            _logger, logging.INFO, "Start BashSession.run", 
            command=command, timeout=timeout, interactive=interactive
        )
        if not isinstance(command, str) or len(command) == 0:
            raise ValueError('Empty command in BashSession.run')
        
        if command in String2Signal:
            self.__send_signal(String2Signal[command])
            log_event(_logger, logging.DEBUG, "done __send_signal", command=command)
        else:
            self.__send_command(command)
            log_event(_logger, logging.DEBUG, "done __send_command", command=command)

        if interactive or self.is_interactive:
            self.is_interactive = True

            log_event(_logger, logging.DEBUG, "start __read_interactive", command=command)
            output = self.__read_interactive()
            
            # the way we get status for non-interactive is `$?`, however this can't be done for 
            # interactive commands so default to UNKNOWN.
            command_output = CommandOutput(output=output, status=CommandStatus.UNKNOWN)
        else:
            log_event(_logger, logging.DEBUG, "start __read", command=command)
            output, command_timed_out = self.__read(read_timeout=timeout)

            # capture status of last executed command
            self.__send_command("printf '%d\n' $?")
            status_result, _ = self.__read()
            status_code = CommandStatus.UNKNOWN
            
            try:
                status_match = self.__status_pattern.search(status_result)
                if status_match:
                    status_no = int(status_match.group(1))
                    status_code = CommandStatus(status_no)
            except (IndexError, ValueError) as status_err:
                log_event(_logger, logging.ERROR, "Failed acquiring status", error=status_err)
            
            log_event(
                _logger, logging.DEBUG, "Captured status_code", command=f"`{command}`", 
                raw_status=f"{repr(status_result)}", status_code=status_code
            )
            command_output = CommandOutput(
                output=output, 
                status=status_code, 
                timed_out=command_timed_out
            )

        log_event(
            _logger, logging.INFO, "Done BashSession.run",
            status=command_output.status, timed_out=command_output.timed_out
        )
        return command_output
            
    def close(self):
        if self.master_fd:
            os.close(self.master_fd)
        if self.process:
            self.process.terminate()

    def __start_session(self):
        self.master_fd, self.slave_fd = pty.openpty()

        # disable ECHO on slave
        slave_attrs_bkup = termios.tcgetattr(self.slave_fd) 
        slave_attrs = list(slave_attrs_bkup)
        slave_attrs[3] = slave_attrs[3] & ~termios.ECHO  # pos 3 is lflag, unset ECHO 
        termios.tcsetattr(self.slave_fd, termios.TCSANOW, slave_attrs)

        # note: just using `shell=True` makes the subprocess close after executing non
        # interactive commands (ex. ls).
        self.process = subprocess.Popen(
            ['/bin/sh', '-i'],
            stdin=self.slave_fd,
            stdout=self.slave_fd,
            stderr=self.slave_fd,
            preexec_fn=_setup_subprocess(fd=self.slave_fd, ps1=self.write_sentinel)
        )
        os.close(self.slave_fd)  # owning process doesn't need the slave

        # check if terminal ready 
        _ = self.__read()
        time.sleep(0.5)

    def __send_command(self, command: str):
        cmd_bytes = (command + '\n').encode()
        sent_bytes = os.write(self.master_fd, cmd_bytes)
        if sent_bytes != len(cmd_bytes):
            log_event(
                _logger, logging.ERROR, "command partially sent",
                sent_bytes=sent_bytes, expected_bytes=len(cmd_bytes)
            )

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

    def __read(self, read_timeout: float = None) -> Tuple[str, bool]:
        command_output = ''
        timed_out = False
        timeout = read_timeout if read_timeout else self.default_timeout

        poller = select.poll()
        poller.register(self.master_fd, select.POLLIN | select.POLLPRI)
        start = time.monotonic()
        while True: 
            # for some reason doing poll(100) has a different behaviour than 
            # sleep -> poll(0) // non-blocking
            time.sleep(0.1)
            events = poller.poll(0)
            for fd, _ in events:
                if fd != self.master_fd:
                    continue

                command_output += strip_ansi(
                    os.read(self.master_fd, 4096).decode('utf-8', errors='replace')
                )
            
            # exit on sentinel
            if self.write_sentinel in command_output:
                command_output = command_output.replace(self.write_sentinel, '')
                break

            # or exit on timeout
            elapsed = time.monotonic() - start
            if elapsed >= timeout:
                timed_out = True
                self.__send_signal(signal.SIGKILL)
                time.sleep(0.1)
                break

        return command_output, timed_out

    def __read_interactive(self) -> str:
        # interactive reads are kind of a pain in the ass, the best solution I could find is 
        # to use an exponential-backoff approach where poll waits `base_delay` seconds doubled 
        # each iteration; after two consecutive empty reads if we have output we return. 
        # note: here there's no concept of timeout.
        poller = select.poll()
        poller.register(self.master_fd, select.POLLIN | select.POLLPRI)
        
        cmd_output = ''
        base_delay = 0.2
        max_delay = 12
        consecutive_empty = 0
        while True:
            events = poller.poll(base_delay * 1000)
            for fd, _ in events:
                # read if any 
                if fd != self.master_fd:
                    continue
                cmd_output += strip_ansi(
                    os.read(self.master_fd, 4096).decode('utf-8', errors='replace')
                )
                consecutive_empty = 0 # reset if new output

            base_delay = base_delay * 2
            if base_delay >= max_delay:
                log_event(
                    _logger, logging.DEBUG, "max_delay reached in interactive read", max_delay=max_delay
                )
                break

            if len(cmd_output) > 0:
                consecutive_empty += 1
                if consecutive_empty >= 2:
                    log_event(_logger, logging.DEBUG, "done reading in interactive read")
                    break

        if self.write_sentinel in cmd_output:
            cmd_output = cmd_output.replace(self.write_sentinel, '')
            self.is_interactive = False
        return cmd_output  

