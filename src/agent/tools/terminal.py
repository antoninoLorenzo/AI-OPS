"""Terminal Tool"""
import platform
import queue
import subprocess
import threading
import time


class Terminal:
    """A stateful terminal implementation"""
    name: str = 'Terminal'
    tool_description: str = f'A {platform.system()} Terminal.'
    args_description: str = f'Takes as argument the string representing the command to execute.'
    use_case: str = 'Terminal Usage'
    SHELLS = {
        'Linux': '/bin/sh',
        'Windows': 'cmd.exe'  # TODO: change with full path
    }

    def __init__(self):
        self.proc = subprocess.Popen(
            self.SHELLS[platform.system()],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
            text=True
        )
        self.reader_output = queue.Queue()

        reader = threading.Thread(target=self.__fetch_output)
        reader.daemon = True
        reader.start()

    def run(self, command: str):
        """Interface to terminal"""
        if not isinstance(command, str):
            raise ValueError(f"command should be str, found '{type(command)}'.")
        self.__exec(command)
        return ''.join(self.read())

    def __exec(self, command: str):
        """Write a command to the terminal standard input"""
        self.proc.stdin.write(f'{command}\n')
        self.proc.stdin.flush()
        time.sleep(0.2)

    def __fetch_output(self):
        """Read the output from terminal standard output"""
        if self.proc.stdout:
            for line in iter(self.proc.stdout.readline, ''):
                self.reader_output.put(line)

            # TODO: handle stderr, not working
            # for line in iter(proc.stderr.readline, ''):
            #     stdout.put(line)
        else:
            print(f'{self.proc.stdout}')

    def read(self):
        """A generator that returns single lines from the terminal output"""
        # wait for output to be added into queue
        while self.reader_output.empty():
            pass

        # read from queue
        while not self.reader_output.empty():
            yield self.reader_output.get()

    def close(self):
        """Clean up the subprocess"""
        if self.proc:
            self.proc.stdin.close()
            self.proc.terminate()
            self.proc.wait()

    def __del__(self):
        self.close()


if __name__ == "__main__":
    term = Terminal()
    print(term.run('ls -la'))
    print(term.run('cd ..'))
    print(term.run('ls -la'))
    term.close()
