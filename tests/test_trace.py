"""Semantic checks for trace accounting; fixture is synthetic, not boot evidence."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    'trace_stats', Path(__file__).resolve().parents[1] / 'tools/trace_stats.py')
trace = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trace)

LOG = '''1 N 0
1 J 0
2 N 1
2 J 1
1 R 2
1 W 5
2 R 5
2 J 8
1 J 9
2 R 9
1 R 10
2 E 12
1 E 14
'''


class TraceTest(unittest.TestCase):
    def test_accounting_and_selected_interval(self):
        result = trace.analyze(LOG, [1, 2])
        first, second = result['processes']
        self.assertEqual([first[k] for k in ('ready_ticks', 'running_ticks',
                         'blocked_ticks', 'turnaround_ticks')], [3, 7, 4, 14])
        self.assertEqual(second['ready_ticks'], 5)
        self.assertEqual(second['running_ticks'], 6)
        self.assertEqual(result['interval_seconds'], .14)
        self.assertAlmostEqual(result['throughput_per_second'], 2 / .14)
        self.assertEqual(result['means']['ready_ticks'], 4)

    def test_unselected_background_can_be_partial(self):
        result = trace.analyze(LOG + '99 R 15\n', [2])
        self.assertEqual(result['interval_start_tick'], 1)
        self.assertEqual(result['interval_end_tick'], 12)

    def test_incomplete_selected(self):
        for log, pids in [(LOG, [3]), (LOG.replace('1 N 0\n', ''), [1]),
                          (LOG.replace('1 E 14\n', ''), [1])]:
            with self.subTest(log=log, pids=pids), self.assertRaises(trace.TraceError):
                trace.analyze(log, pids)

    def test_malformed_order_and_transitions(self):
        invalid = ['1 N 2\n1 J 1\n', '1 N 0\n1 E 0\n',
                   '1 N 0\n1 J 0\n1 J 0\n1 R 0\n1 E 1\n',
                   '1 N 0\n1 J 0\n1 R 0\n1 E 1\n1 R 1\n1 E 2\n',
                   '-1 N 0\n', '1 Z 0\n', '1 N nope\n', '1 N 0 garbage\n']
        for log in invalid:
            with self.subTest(log=log), self.assertRaises(trace.TraceError):
                trace.analyze(log, [1])

    def test_overflow_is_never_accepted(self):
        with self.assertRaises(trace.TraceError):
            trace.analyze(LOG + '# LOST_OR_READ_ERROR\n', [1])

    def test_zero_tick_lifetime(self):
        result = trace.analyze('1 N 5\n1 J 5\n1 R 5\n1 E 5\n', [1])
        self.assertIsNone(result['throughput_per_second'])
        self.assertEqual(result['processes'][0]['turnaround_ticks'], 0)

    def test_creation_accounted_and_bad_selection(self):
        result = trace.analyze('1 N 0\n1 J 1\n1 R 2\n1 E 3\n', [1])
        self.assertEqual(result['processes'][0]['creation_ticks'], 1)
        for ids, hz in [([], 100), ([0], 100), ([1], 0)]:
            with self.assertRaises(trace.TraceError):
                trace.analyze(LOG, ids, hz)


if __name__ == '__main__':
    unittest.main()
