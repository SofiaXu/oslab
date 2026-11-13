#!/usr/bin/env python3
"""Compile freestanding i386 C with Ubuntu GCC and emit Linux 0.11 ZMAGIC.

The suite runtime is intentionally small; never link the host's glibc into a
Linux 0.11 guest! The retained ELF and symbols can be used with GDB.
"""
import argparse
from pathlib import Path
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[1]
GUEST = ROOT / 'tools/guest'
FLAGS = ['-m32', '-march=i386', '-std=gnu89', '-O0', '-g', '-ffreestanding', '-nostdinc',
         '-fno-builtin', '-fno-stack-protector', '-fno-pie', '-fno-pic',
         '-fno-asynchronous-unwind-tables', '-mno-sse', '-mno-mmx', '-mfpmath=387',
         '-mpreferred-stack-boundary=2', '-mincoming-stack-boundary=2',
         '-I' + str(GUEST / 'include')]


def build(source, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    work = output.parent / (output.name + '.objects')
    work.mkdir(exist_ok=True)
    objs = []
    for name, src in [('start', GUEST/'start.S'), ('libc', GUEST/'libc.c'), ('main', source)]:
        obj = work / (name+'.o')
        subprocess.run(['gcc', *FLAGS, '-c', str(src), '-o', str(obj)], check=True)
        objs.append(str(obj))
    elf = output.with_suffix('.elf')
    subprocess.run(['ld', '-m', 'elf_i386', '-T', str(GUEST/'link.ld'), '-o', str(elf), *objs], check=True)
    raw = work / 'payload.bin'
    subprocess.run(['objcopy', '-O', 'binary', str(elf), str(raw)], check=True)
    symbols = {}
    for line in subprocess.check_output(['nm', '-n', str(elf)], text=True).splitlines():
        fields = line.split()
        if len(fields) == 3: symbols[fields[2]] = int(fields[0], 16)
    text = symbols['__text_end']
    data = symbols['__data_end'] - text
    bss = symbols['__bss_end'] - symbols['__data_end']
    payload = raw.read_bytes()
    if len(payload) > text+data: raise ValueError('unexpected ELF section outside text/data')
    header = struct.pack('<8I', 0o413, text, data, bss, 0, symbols['_start'], 0, 0)
    output.write_bytes(header.ljust(1024,b'\0') + payload.ljust(text+data,b'\0'))
    return output


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    build(a.source, a.output)
