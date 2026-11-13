#!/usr/bin/env python3
"""Stdlib behavioral acceptance tests. Run: python3 tests/test_algorithms.py.

OSLAB_IMPL=student|reference (default reference) selects the implementation.
OSLAB_LAB=4|6|7|8 selects one lab; unset runs all labs.
Binaries go to build/labNN/IMPL/labNN, never edit student files.
No third-party Python modules and no root privileges required.
"""
import os
from pathlib import Path
import random
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
LABS = (4, 6, 7, 8)


class Algorithms(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="oslab-algorithms-")
        cls.addClassCleanup(cls.temp.cleanup)
        cls.base = Path(cls.temp.name)
        cls.impl = os.environ.get("OSLAB_IMPL", "reference")
        selected = os.environ.get("OSLAB_LAB")
        if cls.impl not in ("student", "reference"):
            raise ValueError("OSLAB_IMPL must be student or reference")
        if selected is not None and selected not in ("4", "6", "7", "8"):
            raise ValueError("OSLAB_LAB must be 4, 6, 7 or 8")
        cls.bins = {}
        for n in ((int(selected),) if selected is not None else LABS):
            dest = ROOT / f"build/lab{n:02}" / cls.impl
            subprocess.run(["make", "--no-print-directory", "-C", str(ROOT / f"labs/lab{n:02}"),
                            f"IMPL={cls.impl}", f"BUILD_DIR={dest}"], check=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            cls.bins[n] = dest / f"lab{n:02}"

    def run_lab(self, n, *args, data="", status=0):
        p = subprocess.run([str(self.bins[n]), *map(str, args)], input=data,
                           text=True, capture_output=True, timeout=10)
        self.assertEqual(p.returncode, status, p.stdout + p.stderr)
        return p.stdout

    def fixture(self, n, name):
        return ROOT / f"labs/lab{n:02}/fixtures" / name

    def temporary(self, name, contents):
        path = self.base / name
        path.write_text(contents)
        return path

    def test_student_skeletons_are_buildable_and_explicit(self):
        for n in LABS:
            with self.subTest(lab=n):
                dest = ROOT / f"build/lab{n:02}/student"
                subprocess.run(["make", "-s", "-C", str(ROOT / f"labs/lab{n:02}"),
                                "IMPL=student", f"BUILD_DIR={dest}"], check=True)
                p = subprocess.run([str(dest / f"lab{n:02}")], text=True, capture_output=True)
                self.assertEqual(p.returncode, 3)
                self.assertIn("INCOMPLETE", p.stderr)

    def test_banker_rollback_and_subsequent_grant(self):
        out = self.run_lab(4, self.fixture(4, "classic.txt"),
                           data="SHOW\nREQUEST 4 3 3 0\nSHOW\nREQUEST 1 1 0 2\nQUIT\n", status=1)
        self.assertIn("DENIED unsafe_rollback", out)
        # Entire matrix, not only available, must survive failed allocation.
        matrices = re.findall(r"AVAILABLE[^\n]*\nPID MAX \| ALLOC \| NEED\n(?:P[^\n]*\n){5}", out)
        self.assertEqual(matrices[0], matrices[1])
        self.assertEqual(matrices[0], matrices[2])
        self.assertEqual(matrices[0], matrices[3])
        self.assertIn("GRANTED", out)
        self.assertIn("AVAILABLE 2 3 0", out)
        self.assertIn("P1 3 2 2 | 3 0 2 | 0 2 0", out)
        self.assertIn("SAFE P1 P3 P4 P0 P2", out)

    def test_banker_rejections_do_not_change_state(self):
        out = self.run_lab(4, self.fixture(4, "classic.txt"), status=1,
                           data="REQUEST 50 0 0 0\nREQUEST 0 8 0 0\nREQUEST 0 0 0 3\nSHOW\n")
        for reason in ("pid", "exceeds_need", "unavailable"):
            self.assertIn("DENIED " + reason, out)
        self.assertEqual(out.count("AVAILABLE 3 3 2"), 5)

    def test_banker_initial_unsafe_and_malformed(self):
        path = self.temporary("unsafe.txt", "2 1\n0\n2\n2\n1\n1\n")
        self.assertIn("UNSAFE", self.run_lab(4, path))
        for i, text in enumerate(("0 1", "1 1 0 1 2", "1 1 -1 2 0", "1 1 0 1", "1 1 0 1 0 garbage")):
            self.run_lab(4, self.temporary(f"bad-banker-{i}", text), status=2)
        self.run_lab(4, self.fixture(4, "classic.txt"), data="REQUEST 0 -1 0 0", status=2)

    def test_banker_all_processes_must_finish(self):
        path = self.temporary("partially-safe.txt", "2 1\n0\n2\n0\n1\n0\n")
        self.assertIn("UNSAFE", self.run_lab(4, path))

    def admissions(self, out):
        return re.findall(r"^ADMIT (\S+) (\S+) time=(\d+) start=(\d+)$", out, re.M)

    def test_job_original_fcfs_and_sjf(self):
        for policy, expected in (("fcfs", ["ZYA", "ZYB", "ZYD", "ZYC", "ZYE"]),
                                 ("sjf", ["ZYC", "ZYA", "ZYE", "ZYD", "ZYB"])):
            with self.subTest(policy=policy):
                out = self.run_lab(6, policy, "auto", self.fixture(6, "original.txt"))
                self.assertEqual([j[1] for j in self.admissions(out)], expected)
                self.assertIn("STATE time=84 resident=0 tapes_free=5", out)
                self.assertTrue(out.endswith("HOLE start=0 size=100\nALL_DONE\n"))
                self.assertEqual(out.count("\nCOMPLETE "), 5)

    def test_job_fragmentation_skip_and_coalescing(self):
        out = self.run_lab(6, "fcfs", "manual", self.fixture(6, "fragmentation.txt"),
                           data=self.fixture(6, "manual.txt").read_text())
        admits = self.admissions(out)
        self.assertEqual([(a[1], int(a[3])) for a in admits], [("A", 0), ("B", 30), ("D", 0), ("C", 0)])
        # After A leaves, free total=60 but largest hole=30, so C=50 cannot enter.
        self.assertIn("HOLE start=0 size=30\nHOLE start=70 size=30", out)
        self.assertIn("JOB C C RESIDENT", out)
        self.assertNotIn("COMPLETE C C", out)

    def test_job_tapes_skip_ties_and_cpu_model(self):
        path = self.temporary("tapes.txt", "A a 3 10 4\nB b 1 10 2\nC c 1 10 1\n")
        fcfs = self.run_lab(6, "fcfs", "auto", path)
        self.assertEqual([x[1] for x in self.admissions(fcfs)], ["a", "c", "b"])
        self.assertIn("COMPLETE A a time=3", fcfs)
        self.assertIn("COMPLETE C c time=4", fcfs)  # Resident c does not execute in parallel.
        sjf = self.run_lab(6, "sjf", "auto", path)
        self.assertEqual([x[1] for x in self.admissions(sjf)], ["b", "c", "a"])

    def test_job_invalid_inputs_and_manual_failure(self):
        out = self.run_lab(6, "fcfs", "manual", self.fixture(6, "original.txt"),
                           data="COMPLETE A ZYA\nWRONG\nADMIT\nCOMPLETE A ZYA\nCOMPLETE A ZYA\n", status=1)
        self.assertEqual(out.count("DENIED not_resident"), 2)
        self.assertIn("DENIED command", out)
        for i, text in enumerate(("A a 0 10 1", "A a 1 101 1", "A a 1 10 6", "A a 1 10 1\nA a 2 20 2", "")):
            self.run_lab(6, "fcfs", "auto", self.temporary(f"bad-job-{i}", text), status=2)

    @staticmethod
    def page_oracle(pages, cap, alg):
        # Independent dict model; insertion ordered for FIFO and LFU ties.
        resident = {}
        faults = replacements = 0
        trace = []
        for t, page in enumerate(pages):
            victim = -1
            hit = page in resident
            if not hit:
                faults += 1
                if len(resident) == cap:
                    if alg == "fifo":
                        victim = next(iter(resident))
                    elif alg == "lru":
                        victim = min(resident, key=lambda p: resident[p][0])
                    else:
                        victim = min(resident, key=lambda p: resident[p][1])
                    del resident[victim]
                    replacements += 1
                resident[page] = [t, 0]
            resident[page][0] = t
            resident[page][1] += 1
            trace.append((hit, victim, faults, replacements))
        return trace

    def test_pages_original_sequences_and_all_frame_sizes(self):
        for name in ("sequence1.txt", "sequence2.txt", "lfu-tie.txt"):
            path = self.fixture(7, name)
            pages = list(map(int, path.read_text().split()))
            for cap in (1, 3, 4, 5):
                for alg in ("fifo", "lru", "lfu"):
                    with self.subTest(sequence=name, frames=cap, alg=alg):
                        out = self.run_lab(7, "run", alg, cap, path)
                        rows = re.findall(r"^STEP \d+ page=\d+ (HIT|FAULT) victim=(-?\d+) frames=\S+ faults=(\d+) replacements=(\d+)", out, re.M)
                        trace = [(h == "HIT", int(v), int(f), int(r)) for h, v, f, r in rows]
                        self.assertEqual(trace, self.page_oracle(pages, cap, alg))
        out = self.run_lab(7, "run", "fifo", 3, self.fixture(7, "sequence1.txt"))
        self.assertIn("faults=15 replacements=12 fault_rate=0.750000 replacement_rate=0.600000", out)

    def test_pages_randomized_oracle(self):
        rng = random.Random(482)
        for case in range(12):
            pages = [rng.randrange(9) for _ in range(90)]
            path = self.temporary(f"random-{case}", " ".join(map(str, pages)))
            cap = rng.randrange(1, 7)
            out = self.run_lab(7, "run", "all", cap, path)
            for alg in ("fifo", "lru", "lfu"):
                _, _, faults, replacements = self.page_oracle(pages, cap, alg)[-1]
                self.assertIn(f"SUMMARY alg={alg} frames={cap} references=90 faults={faults} replacements={replacements}", out)

    def test_pages_generate_save_replay_step_stdin(self):
        p, q = self.base / "generated", self.base / "saved"
        self.run_lab(7, "generate", 123, 20, 10, p)
        seq = p.read_text()
        self.run_lab(7, "generate", 123, 20, 10, q)
        self.assertEqual(seq, q.read_text())
        out = self.run_lab(7, "run", "all", 3, p, "--save", q)
        self.assertEqual(seq, q.read_text())
        self.assertEqual(out, self.run_lab(7, "run", "all", 3, q))
        self.assertEqual(out, self.run_lab(7, "run", "all", 3, "-", data=seq))
        step = self.run_lab(7, "run", "fifo", 3, p, "--step", data="\n" * 20)
        self.assertEqual(step, self.run_lab(7, "run", "fifo", 3, p))
        self.run_lab(7, "run", "fifo", 3, p, "--step", data="\n", status=2)

    def test_pages_invalid_inputs(self):
        self.run_lab(7, "run", "fifo", 0, self.fixture(7, "sequence1.txt"), status=2)
        self.run_lab(7, "run", "bad", 3, self.fixture(7, "sequence1.txt"), status=2)
        for i, text in enumerate(("", "1 -1", "1 x", "99999999999999999999999999999999")):
            self.run_lab(7, "run", "lru", 3, self.temporary(f"bad-pages-{i}", text), status=2)
        self.run_lab(7, "generate", 1, 10, 0, self.base / "bad-output", status=2)
        self.run_lab(7, "run", "fifo", 3, "-", "--step", status=2)

    def test_files_normal_session_isolation_and_exec(self):
        out = self.run_lab(8, data=self.fixture(8, "session.txt").read_text())
        self.assertIn("DATA hello", out)
        self.assertIn("EXEC_SIMULATED alice/app", out)
        self.assertIn("FILE alice app perm=--x open=1 length=0", out)
        self.assertIn("FILE bob notes perm=r-- open=1 length=0", out)
        self.assertIn("USER alice opens=1 limit=2", out)
        self.assertIn("USER bob opens=1 limit=2", out)

    def test_files_denials_preserve_state(self):
        out = self.run_lab(8, data=self.fixture(8, "denied.txt").read_text(), status=1)
        for reason in ("permission", "file_open", "open_limit", "no_such_file"):
            self.assertIn("DENIED " + reason, out)
        self.assertIn("FILE alice readonly perm=r-- open=1 length=0", out)
        self.assertIn("USER bob opens=0 limit=2", out)

    def test_files_limit_close_delete_and_identity(self):
        out = self.run_lab(8, 1, data="""USER a
USER b
LOGIN a
CREATE f rwx
CREATE g rw
OPEN f
OPEN f
OPEN g
CLOSE f
OPEN g
DELETE g
CLOSE g
DELETE g
LOGIN b
CREATE f x
OPEN f
READ f
EXEC f
LOGIN a
OPEN f
WRITE f payload
READ f
LIST
""", status=1)
        for reason in ("already_open", "open_limit", "file_open", "permission"):
            self.assertIn("DENIED " + reason, out)
        self.assertIn("DATA payload", out)
        self.assertIn("FILE a f perm=rwx open=1 length=7", out)
        self.assertIn("FILE b f perm=--x open=1 length=0", out)
        self.assertNotIn("FILE a g", out)

    def test_files_invalid_commands_capacity_and_lengths(self):
        out = self.run_lab(8, data="""CREATE f r
USER a
USER a
LOGIN missing
LOGIN a
CREATE f rr
CREATE ../bad rw
CREATE f rw
CREATE f rw
READ f
CLOSE f
OPEN f
WRITE f one two
WRITE f """ + "x" * 1025 + "\nLIST\n", status=1)
        for reason in ("login_required", "user_exists", "unknown_user", "invalid_name_or_permissions",
                       "file_exists", "not_open", "command", "content_capacity"):
            self.assertIn("DENIED " + reason, out)
        self.assertIn("FILE a f perm=rw- open=1 length=0", out)
        commands = "USER a\nLOGIN a\n" + "".join(f"CREATE f{i} r\n" for i in range(33)) + "LIST\n"
        out = self.run_lab(8, data=commands, status=1)
        self.assertIn("DENIED file_capacity", out)
        self.assertEqual(len(re.findall(r"^FILE ", out, re.M)), 32)
        out = self.run_lab(8, data="".join(f"USER u{i}\n" for i in range(17)), status=1)
        self.assertIn("DENIED user_capacity", out)
        self.run_lab(8, 0, status=2)
        self.run_lab(8, 33, status=2)


def load_tests(loader, standard_tests, pattern):
    """Filter before setUpClass, so a lab-specific check builds only that lab.

    The skeleton infrastructure assertion is not a behavioral grading rule:
    explicit selection of either variable excludes it.
    """
    selected = os.environ.get("OSLAB_LAB")
    prefixes = {"4": "test_banker_", "6": "test_job_",
                "7": "test_pages_", "8": "test_files_"}
    infrastructure = "OSLAB_IMPL" not in os.environ and selected is None
    names = loader.getTestCaseNames(Algorithms)
    return unittest.TestSuite(Algorithms(name) for name in names
                             if (name != "test_student_skeletons_are_buildable_and_explicit" or infrastructure)
                             and (selected is None or selected not in prefixes or
                                  name.startswith(prefixes[selected])))


if __name__ == "__main__":
    unittest.main(verbosity=2)
