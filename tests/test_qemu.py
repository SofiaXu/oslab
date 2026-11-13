"""Startup failures must release image locks and child processes."""
import fcntl
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from qemu import Machine


class StartupCleanup(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='oslab-qemu-test-')
        self.addCleanup(self.temp.cleanup)
        self.disk=Path(self.temp.name)/'disk.img'
        self.disk.write_bytes(bytes(1024))
        self.log=Path(self.temp.name)/'qemu.log'

    def assert_unlocked(self):
        with self.disk.open('r+b') as f:
            fcntl.flock(f,fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_missing_executable_releases_disk(self):
        with patch('qemu.subprocess.Popen',side_effect=FileNotFoundError('no QEMU')):
            with self.assertRaisesRegex(FileNotFoundError,'no QEMU'):
                Machine('missing-kernel',self.disk,log=self.log)
        self.assert_unlocked()

    def test_early_child_exit_before_qmp_releases_disk(self):
        class Exited:
            def poll(self): return 1
        with patch('qemu.subprocess.Popen',return_value=Exited()):
            with self.assertRaisesRegex(RuntimeError,'exited during startup'):
                Machine('missing-kernel',self.disk,log=self.log)
        self.assert_unlocked()

    def test_connection_failure_terminates_child_without_stream(self):
        class Running:
            terminated=False
            def poll(self): return 0 if self.terminated else None
            def terminate(self): self.terminated=True
            def wait(self,timeout=None): return 0
        process=Running()
        with patch('qemu.subprocess.Popen',return_value=process), \
             patch('qemu.socket.socket') as factory:
            factory.return_value.connect.side_effect=OSError('bad QMP socket')
            with self.assertRaisesRegex(OSError,'bad QMP socket'):
                Machine('missing-kernel',self.disk,log=self.log)
        self.assertTrue(process.terminated)
        factory.return_value.close.assert_called_once()
        self.assert_unlocked()


if __name__=='__main__': unittest.main()
