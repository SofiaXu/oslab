#!/usr/bin/env python3
"""Validate real Linux 0.11 PID/state/tick records and summarize selected PIDs."""
import argparse
import json
from pathlib import Path


class TraceError(ValueError):
    """Measurement is malformed or incomplete; never silently interpolate."""


def parse_trace(text):
    records = {}
    previous_tick = -1
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        if line.startswith('#'):
            if any(word in line.upper() for word in ('LOST', 'OVERFLOW', 'ERROR')):
                raise TraceError(f'line {number}: collector reports lost records')
            continue
        parts = line.split()
        if len(parts) != 3:
            raise TraceError(f'line {number}: expected PID STATE TICK')
        try:
            pid, tick = int(parts[0]), int(parts[2])
        except ValueError as exc:
            raise TraceError(f'line {number}: PID/tick must be integers') from exc
        state = parts[1]
        if pid < 0 or tick < 0 or state not in ('N', 'J', 'R', 'W', 'E'):
            raise TraceError(f'line {number}: invalid PID/state/tick')
        if tick < previous_tick:
            raise TraceError(f'line {number}: ticks move backwards (or wrapped)')
        previous_tick = tick
        records.setdefault(pid, []).append((state, tick))
    return records


def analyze(text, pids, hz=100):
    if hz <= 0:
        raise TraceError('HZ must be positive')
    selected = sorted(set(pids))
    if not selected or any(pid <= 0 for pid in selected):
        raise TraceError('select at least one non-idle PID')
    records = parse_trace(text)
    transitions = {'N': {'J'}, 'J': {'R'}, 'R': {'J', 'W', 'E'},
                   'W': {'J'}, 'E': set()}
    results = []
    for pid in selected:
        events = records.get(pid, [])
        if not events or events[0][0] != 'N' or events[-1][0] != 'E':
            raise TraceError(f'PID {pid}: incomplete lifetime (need N through E)')
        totals = {'N': 0, 'J': 0, 'R': 0, 'W': 0}
        for (old, start), (new, end) in zip(events, events[1:]):
            if new not in transitions[old]:
                raise TraceError(f'PID {pid}: invalid transition {old}->{new}')
            if end < start:
                raise TraceError(f'PID {pid}: ticks move backwards')
            totals[old] += end - start
        birth, end = events[0][1], events[-1][1]
        turnaround = end - birth
        if sum(totals.values()) != turnaround:
            raise TraceError(f'PID {pid}: inconsistent lifetime')
        results.append(dict(pid=pid, birth_tick=birth, exit_tick=end,
                            creation_ticks=totals['N'], ready_ticks=totals['J'],
                            running_ticks=totals['R'], blocked_ticks=totals['W'],
                            turnaround_ticks=turnaround))
    start = min(row['birth_tick'] for row in results)
    end = max(row['exit_tick'] for row in results)
    elapsed = (end - start) / hz
    means = {key: sum(row[key] for row in results) / len(results)
             for key in ('ready_ticks', 'running_ticks', 'blocked_ticks',
                         'turnaround_ticks')}
    return dict(hz=hz, processes=results, means=means,
                interval_start_tick=start, interval_end_tick=end,
                interval_seconds=elapsed,
                throughput_per_second=len(results) / elapsed if elapsed else None)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('log', type=Path)
    parser.add_argument('--pids', nargs='+', required=True, type=int,
                        help='exact CHILD/SELECTED PIDs printed by process')
    parser.add_argument('--hz', type=int, default=100)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args(argv)
    try:
        report = analyze(args.log.read_text(encoding='utf-8'), args.pids, args.hz)
    except (OSError, UnicodeError, TraceError) as exc:
        parser.exit(1, f'trace rejected: {exc}\n')
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print('PID\tRUN\tREADY\tBLOCKED\tNEW\tTURNAROUND (ticks)')
        for row in report['processes']:
            print('{pid}\t{running_ticks}\t{ready_ticks}\t{blocked_ticks}\t'
                  '{creation_ticks}\t{turnaround_ticks}'.format(**row))
        print('mean ticks:', report['means'])
        print('interval: [{}, {}], {:.3f}s, throughput: {} processes/s'.format(
            report['interval_start_tick'], report['interval_end_tick'],
            report['interval_seconds'], report['throughput_per_second']))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
