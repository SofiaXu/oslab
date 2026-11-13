#!/usr/bin/env python3
"""Host POSIX process tests; stdlib only. PC=/absolute/pc tests a supplied binary."""
import os
from pathlib import Path
import re
import signal
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ProducerConsumerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory(prefix="oslab-pc-build-")
        supplied = os.environ.get("PC")
        cls.pc = str(Path(supplied).resolve()) if supplied else str(Path(cls.build.name) / "pc")
        if not supplied:
            subprocess.run(["make", "-C", str(ROOT / "labs/lab02"),
                            "IMPL=reference", "BUILD_DIR=" + cls.build.name], check=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)

    @classmethod
    def tearDownClass(cls):
        cls.build.cleanup()

    def spawn(self, *args):
        p = subprocess.Popen([self.pc, *map(str, args)], stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True, start_new_session=True)
        self.addCleanup(self.terminate, p)
        return p

    @staticmethod
    def terminate(p):
        # Also reap peers if a regression strands them after parent death.
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        p.communicate(timeout=5)
        p.stdout.close()
        p.stderr.close()

    def finish(self, p, timeout=15):
        try:
            return p.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.fail("producer/consumer hung (timeout)")

    def assert_clean(self, path, stderr):
        self.assertFalse(Path(path).exists(), "ring file leaked")
        names = re.findall(r"(?:empty|full|mutex)=(/oslab_pc_\S+)", stderr)
        self.assertEqual(len(names), 3, stderr)
        for name in names:
            self.assertFalse((Path("/dev/shm") / ("sem." + name[1:])).exists(),
                             "named semaphore leaked: " + name)

    def assert_ordered(self, stdout, maximum, consumers):
        rows = stdout.splitlines()
        self.assertEqual(len(rows), maximum + 1)
        parsed = [re.fullmatch(r"([1-9][0-9]*):([0-9]+)", row) for row in rows]
        self.assertTrue(all(parsed), "stdout must contain only PID:number lines")
        self.assertEqual([int(row[2]) for row in parsed], list(range(maximum + 1)))
        self.assertEqual(len({row[1] for row in parsed}), consumers)

    def test_ordered_exactly_once_multiple_sizes(self):
        for n, maximum in [(2, 500), (3, 997), (8, 5000), (17, 1201)]:
            with self.subTest(consumers=n, maximum=maximum), tempfile.TemporaryDirectory() as d:
                path = Path(d) / "ring"
                p = self.spawn("--consumers", n, "--max", maximum, "--file", path)
                out, err = self.finish(p)
                self.assertEqual(p.returncode, 0, err)
                self.assert_ordered(out, maximum, n)
                self.assert_clean(path, err)

    def test_defaults(self):
        p = self.spawn()
        out, err = self.finish(p)
        self.assertEqual(p.returncode, 0, err)
        self.assert_ordered(out, 500, 3)
        path = re.search(r"RESOURCES file=(.*?) empty=", err)[1]
        self.assert_clean(path, err)

    def test_invalid_options(self):
        for args in [("--consumers", "1"), ("--consumers", "129"),
                     ("--max", "499"), ("--max", "2147483647"),
                     ("--max", "500garbage"), ("--max", "-1"),
                     ("--file",), ("--unknown",)]:
            with self.subTest(args=args):
                p = self.spawn(*args)
                out, _ = self.finish(p)
                self.assertEqual(p.returncode, 2)
                self.assertEqual(out, "")

    def test_existing_file_is_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "keep"
            path.write_bytes(b"do not truncate me")
            p = self.spawn("--file", path)
            self.finish(p)
            self.assertNotEqual(p.returncode, 0)
            self.assertEqual(path.read_bytes(), b"do not truncate me")

    def running_children(self, p):
        # Linux /proc exposes actual forked processes, not printed fake PIDs.
        until = time.monotonic() + 5
        while time.monotonic() < until:
            try:
                ids = [int(x) for x in Path(f"/proc/{p.pid}/task/{p.pid}/children").read_text().split()]
            except FileNotFoundError:
                ids = []
            if len(ids) == 5:
                return ids
            if p.poll() is not None:
                self.fail("program exited before fault injection")
            time.sleep(.01)
        self.fail("expected one producer and four consumer processes")

    def fault_run(self, action):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "ring"
            # Do not drain stdout yet: pipe backpressure keeps workers alive.
            p = self.spawn("--file", path, "--max", 1000000, "--consumers", 4)
            children = self.running_children(p)
            action(p, children)
            _, err = self.finish(p, timeout=5)
            self.assertNotEqual(p.returncode, 0)
            self.assert_clean(path, err)
            for child in children:
                self.assertFalse(Path(f"/proc/{child}").exists(), "unreaped child")

    def test_parent_sigint_cleanup(self):
        self.fault_run(lambda p, _: os.kill(p.pid, signal.SIGINT))

    def test_parent_sigterm_cleanup(self):
        self.fault_run(lambda p, _: os.kill(p.pid, signal.SIGTERM))

    def test_killed_child_cancels_even_stopped_peers(self):
        def kill_child(p, children):
            for child in children:
                os.kill(child, signal.SIGSTOP)
            os.kill(children[-1], signal.SIGKILL)
        self.fault_run(kill_child)

    def test_child_sigterm_interrupts_wait(self):
        self.fault_run(lambda p, children: os.kill(children[-1], signal.SIGTERM))

    def test_broken_stdout_cancels_workers(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "ring"
            p = self.spawn("--file", path, "--max", 1000000)
            p.stdout.close()
            p.stdout = open(os.devnull)
            p.wait(timeout=5)
            err = p.stderr.read()
            self.assertNotEqual(p.returncode, 0)
            self.assert_clean(path, err)

    def test_unsafe_is_bounded_comparison(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "ring"
            p = self.spawn("--unsafe", "--consumers", 8, "--max", 500, "--file", path)
            out, err = self.finish(p)
            self.assertEqual(p.returncode, 0, err)
            self.assertEqual(len(out.splitlines()), 501)
            # A race is not guaranteed on any particular execution/scheduler.
            self.assert_clean(path, err)

    def test_parallel_runs_do_not_collide(self):
        a, b = self.spawn(), self.spawn()
        for p in (a, b):
            out, err = self.finish(p)
            self.assertEqual(p.returncode, 0, err)
            self.assert_ordered(out, 500, 3)
            self.assert_clean(re.search(r"RESOURCES file=(.*?) empty=", err)[1], err)


if __name__ == "__main__":
    unittest.main()
