#!/usr/bin/env python3
"""QEMU TCG runner. QMP reads actual VGA memory; no fabricated serial console."""
import fcntl
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time


class Machine:
    def __init__(self, kernel, disk, display='none', debug=False, log=None):
        self.temp = self.disk_file = self.log = self.socket = self.stream = self.process = None
        try:
            self.temp = tempfile.TemporaryDirectory(prefix='oslab-qmp-')
            self.disk_file = Path(disk).open('r+b')
            fcntl.flock(self.disk_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.log = open(log or Path(self.temp.name)/'qemu.log', 'w+b')
            cmd = ['qemu-system-i386', '-accel', 'tcg', '-cpu', '486', '-m', '16M',
                   '-drive', f'file={Path(kernel).resolve()},format=raw,if=floppy',
                   '-drive', f'file={Path(disk).resolve()},format=raw,if=ide',
                   '-boot', 'a', '-display', display, '-no-reboot', '-nic', 'none',
                   '-qmp', f'unix:{self.temp.name}/qmp,server=on,wait=off']
            if debug: cmd += ['-gdb', 'tcp:127.0.0.1:1234', '-S']
            self.process = subprocess.Popen(cmd, stderr=self.log)
            self.socket = socket.socket(socket.AF_UNIX)
            self.socket.settimeout(5)
            until = time.monotonic()+10
            while True:
                try: self.socket.connect(self.temp.name+'/qmp'); break
                except (FileNotFoundError, ConnectionRefusedError):
                    if self.process.poll() is not None: raise RuntimeError('QEMU exited during startup')
                    if time.monotonic()>until: raise TimeoutError('QMP startup timeout')
                    time.sleep(.05)
            self.stream = self.socket.makefile('rwb', buffering=0)
            self.stream.readline()
            self.execute('qmp_capabilities')
        except BaseException:
            self.close(); raise

    def __enter__(self): return self
    def __exit__(self, *args): self.close()

    def execute(self, name, arguments=None):
        cmd = {'execute': name}
        if arguments is not None: cmd['arguments'] = arguments
        self.stream.write(json.dumps(cmd).encode()+b'\n')
        while True:
            line = self.stream.readline()
            if not line: raise RuntimeError('QEMU closed QMP')
            response = json.loads(line)
            if 'error' in response: raise RuntimeError(response['error'])
            if 'return' in response: return response['return']

    def hmp(self, command):
        result = self.execute('human-monitor-command', {'command-line': command})
        if result: raise RuntimeError(result.strip())

    def screen(self):
        path = Path(self.temp.name)/'vga'
        self.hmp(f'pmemsave 0xb8000 4000 "{path}"')
        chars = path.read_bytes()[::2]
        return '\n'.join(chars[i:i+80].decode('cp437').rstrip() for i in range(0,2000,80))

    def wait_for(self, marker, timeout=60):
        until = time.monotonic()+timeout
        last = ''
        while time.monotonic()<until:
            if self.process.poll() is not None: raise RuntimeError('QEMU exited before '+marker+'\n'+last)
            last = self.screen()
            if marker in last: return last
            time.sleep(.15)
        raise TimeoutError('Guest timeout waiting for '+marker+'\n'+last)

    def type_line(self, text):
        # HMP QKeyCode names; enough for shell commands, not keyboard-layout guessing.
        special = {' ': 'spc', '/':'slash', '.':'dot', '-':'minus', '_':'shift-minus',
                   '>':'shift-dot', '<':'shift-comma', ':':'shift-semicolon', ';':'semicolon',
                   '=':'equal', '|':'shift-backslash', '&':'shift-7', '?':'shift-slash'}
        for c in text:
            key = special.get(c, 'shift-'+c.lower() if c.isupper() else c)
            self.hmp('sendkey '+key+' 10')
            time.sleep(.025)
        self.hmp('sendkey ret')

    def close(self):
        if self.process is not None and self.process.poll() is None:
            try:
                if self.stream is not None: self.execute('quit')
                else: self.process.terminate()
            except (OSError, RuntimeError): self.process.terminate()
            try: self.process.wait(timeout=5)
            except subprocess.TimeoutExpired: self.process.kill();self.process.wait()
        if self.stream is not None: self.stream.close()
        if self.socket is not None: self.socket.close()
        if self.disk_file is not None: self.disk_file.close()
        if self.log is not None: self.log.close()
        if self.temp is not None: self.temp.cleanup()
