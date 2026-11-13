#!/usr/bin/env python3
"""Lab 5 ABI checks on real i386 objects; no QEMU/boot claims are made here."""
from pathlib import Path
import argparse
import os
import sys
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
FLAGS = ['-m32', '-march=i386', '-std=gnu89', '-O0', '-ffreestanding', '-fno-builtin',
         '-fno-stack-protector', '-fno-pie', '-fno-pic', '-fomit-frame-pointer',
         '-mno-sse', '-mno-mmx', '-msoft-float',
         '-mpreferred-stack-boundary=2', '-mincoming-stack-boundary=2']


def run(args, cwd=None):
    p = subprocess.run(list(map(str, args)), cwd=cwd, text=True,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
    if p.returncode:
        raise AssertionError(' '.join(map(str, args)) + '\n' + p.stdout)
    return p.stdout


def check_software_switch(obj):
    """Reject a compiled hardware fallback, even after its TODO was deleted.

    This is a structural regression gate for this lab's documented interface,
    not a proof of semantic correctness. Real QEMU acceptance is also required.
    Raises AssertionError with an actionable message; returns the disassembly.
    """
    dis = run(['objdump', '-dr', obj])
    if 'elf32-i386' not in dis or '<lab5_switch>:' not in dis:
        raise AssertionError('expected an i386 object defining lab5_switch')
    if re.search(r'\bl(?:jmp|call|tr)\w*\b', dis):
        raise AssertionError('hardware task switch detected (ljmp/lcall/ltr)')
    for pattern, why in [
        (r'\blldt\b', 'new LDT must be installed'),
        (r'\bcli\b', 'interrupts must be disabled during the switch'),
        (r'\bclts\b', 'live x87 owner needs lazy-FPU handling'),
        (r'\bmov\s+%esp,[^\n]+\(', 'outgoing kernel ESP must be saved'),
        (r'\bmov\s+[^,\n]+\([^\n]+\),%esp', 'incoming kernel ESP must be loaded'),
        (r'\bmov\s+%[a-z]+,%cr0', 'software switch must manage CR0.TS'),
    ]:
        if not re.search(pattern, dis):
            raise AssertionError('software-switch gate: ' + why)
    if re.search(r'\bsti\b', dis):
        raise AssertionError('restore saved IF; do not unconditionally STI')
    fs = re.search(r'\bpop\s+%fs', dis)
    ldt = re.search(r'\blldt\b', dis)
    if fs is None or fs.start() < ldt.start():
        raise AssertionError('restore FS only after loading the new LDT')
    return dis


class StackLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (ROOT / 'labs/lab05/reference/kernel').is_dir():
            raise unittest.SkipTest('reference implementation omitted from student archive; '
                                   'use make check-lab5 for the student software switch')
        for name in ('gcc', 'ld', 'make', 'patch', 'objdump'):
            if not shutil.which(name):
                raise unittest.SkipTest('apt install build-essential binutils patch: ' + name)
        cls.scratch = tempfile.TemporaryDirectory(prefix='oslab-stack-')
        cls.addClassCleanup(cls.scratch.cleanup)
        cls.trees = {}
        for impl in ('reference', 'student'):
            dst = Path(cls.scratch.name) / impl
            dst.mkdir()
            for folder in ('include', 'kernel'):
                shutil.copytree(ROOT / 'vendor/linux-0.11' / folder, dst / folder,
                                ignore=shutil.ignore_patterns('*.o', '*.a', '*.inc'))
            shutil.copy(ROOT / 'vendor/linux-0.11/Makefile.header', dst)
            run(['patch', '--batch', '-p1', '-i', ROOT / 'labs/lab05/kernel.patch'], dst)
            for src in (ROOT / 'labs/lab05' / impl / 'kernel').iterdir():
                shutil.copy(src, dst / 'kernel' / src.name)
            cls.trees[impl] = dst

    def test_reference_and_student_kernel_objects_link(self):
        for impl, tree in self.trees.items():
            with self.subTest(impl=impl):
                run(['make', '-C', tree / 'kernel', 'kernel.o'])
                self.assertTrue((tree / 'kernel/kernel.o').exists())

    def test_i386_fork_frame_and_original_offsets(self):
        tree = self.trees['reference']
        # Execute only nonprivileged frame construction. No host libc/multilib
        # runtime is needed: _start exits via Linux i386 int 0x80.
        source = tree / 'frame_test.c'
        source.write_text(r'''
#include "kernel/lab5.h"
#define CHECK(c) do { if (!(c)) return __LINE__; } while (0)
#define OFF(t,m) __builtin_offsetof(t,m)
typedef char word_is_4[(sizeof(unsigned long)==4)?1:-1];
typedef char frame_is_88[(sizeof(struct lab5_fork_frame)==88)?1:-1];
typedef char switch_is_40[(sizeof(struct lab5_switch_frame)==40)?1:-1];
typedef char syscall_is_48[(sizeof(struct lab5_syscall_frame)==48)?1:-1];
static unsigned char page[PAGE_SIZE] __attribute__((aligned(PAGE_SIZE)));
void lab5_fork_return(void) {}
int test(void) {
    struct task_struct *p = (struct task_struct *)page;
    struct lab5_fork_frame *f;
    CHECK(OFF(struct task_struct,state)==0);
    CHECK(OFF(struct task_struct,counter)==4);
    CHECK(OFF(struct task_struct,blocked)==528);
    CHECK(OFF(struct task_struct,kernel_esp)==
          OFF(struct task_struct,tss)+sizeof(struct tss_struct));
    CHECK(OFF(struct lab5_switch_frame,eip)==36);
    CHECK(OFF(struct lab5_syscall_frame,eip)==28);
    CHECK(OFF(struct lab5_syscall_frame,ss)==44);
    lab5_init_stack(p, 11,12,13,0x17, 14,15,16,0x17,0x17,0x17,
                    0x12345678,0xf,0x202,0x87654320,0x17);
    CHECK(p->kernel_esp==(unsigned long)page+PAGE_SIZE-88);
    f=(struct lab5_fork_frame *)p->kernel_esp;
    CHECK(f->sw.gs==0x17 && f->sw.fs==0x17);
    CHECK(f->sw.es==0x10 && f->sw.ds==0x10);
    CHECK(f->sw.edi==12 && f->sw.esi==13 && f->sw.ebp==11);
    CHECK(f->sw.ebx==14 && f->sw.eflags==2);
    CHECK(f->sw.eip==(unsigned long)lab5_fork_return);
    CHECK(f->user.eax==0 && f->user.ebx==14);
    CHECK(f->user.ecx==15 && f->user.edx==16);
    CHECK(f->user.fs==0x17 && f->user.es==0x17 && f->user.ds==0x17);
    CHECK(f->user.eip==0x12345678 && f->user.cs==0xf);
    CHECK(f->user.eflags==0x202 && f->user.esp==0x87654320);
    CHECK(f->user.ss==0x17);
    return 0;
}
__asm__(".globl _start\n_start:\ncall test\nmovl %eax,%ebx\n"
        "movl $1,%eax\nint $0x80\n");
''')
        gcc = ['gcc', *FLAGS, '-I' + str(tree / 'include'), '-I' + str(tree)]
        run([*gcc, '-c', source, '-o', tree / 'frame_test.o'])
        run([*gcc, '-c', tree / 'kernel/lab5.c', '-o', tree / 'frame_impl.o'])
        run(['ld', '-m', 'elf_i386', '-e', '_start', '-o', tree / 'frame_test',
             tree / 'frame_test.o', tree / 'frame_impl.o'])
        try:
            result = subprocess.run([str(tree / 'frame_test')], timeout=10)
        except OSError as exc:
            if exc.errno == 8:
                self.skipTest('host lacks IA32 execution; compile-time ABI checks passed')
            raise
        self.assertEqual(result.returncode, 0, 'frame assertion line (modulo 256)')

    def test_software_object_has_no_hardware_switch(self):
        tree = self.trees['reference']
        run(['make', '-C', tree / 'kernel', 'lab5_switch.o'])
        dis = check_software_switch(tree / 'kernel/lab5_switch.o')
        self.assertNotRegex(dis, r'\bljmp\b|\blcall\b')
        self.assertRegex(dis, r'\blldt\b')
        self.assertRegex(dis, r'\bclts\b')
        self.assertRegex(dis, r'\bcli\b')
        self.assertNotRegex(dis, r'\bsti\b')
        self.assertLess(dis.index('lldt'), dis.index('pop    %fs'))
        offsets = (tree / 'kernel/lab5_offsets.inc').read_text()
        self.assertRegex(offsets, r'LAB5_NEXT,\s*36')
        self.assertRegex(offsets, r'LAB5_TSS_ESP0,\s*4')
        self.assertRegex(offsets, r'LAB5_PAGE_SIZE,\s*4096')

    @unittest.skipIf(os.getenv('OSLAB_IMPL') == 'student', 'release-scaffold check; completed student code may replace it')
    def test_hardware_fallback_rejected_even_without_todo(self):
        tree = self.trees['student']
        for name in ('lab5_switch.S', 'lab5.c'):
            path = tree / 'kernel' / name
            path.write_text(path.read_text().replace('TODO_LAB5_SOFTWARE_SWITCH', ''))
        run(['make', '-C', tree / 'kernel', 'lab5_switch.o'])
        with self.assertRaisesRegex(AssertionError, 'hardware task switch'):
            check_software_switch(tree / 'kernel/lab5_switch.o')

    @unittest.skipIf(os.getenv('OSLAB_IMPL') == 'student', 'release-scaffold check; completion is allowed')
    def test_student_is_explicitly_incomplete(self):
        student = ROOT / 'labs/lab05/student/kernel'
        self.assertIn('TODO_LAB5_SOFTWARE_SWITCH', (student / 'lab5.c').read_text())
        self.assertIn('TODO_LAB5_SOFTWARE_SWITCH', (student / 'lab5_switch.S').read_text())
        self.assertIn('ljmp', (student / 'lab5_switch.S').read_text())
        reference = ROOT / 'labs/lab05/reference/kernel'
        self.assertNotIn('TODO_LAB5_SOFTWARE_SWITCH', ''.join(
            p.read_text() for p in reference.iterdir()))


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--check-switch':
        parser = argparse.ArgumentParser(description='Check a built lab5_switch.o')
        parser.add_argument('--check-switch', type=Path, required=True)
        args = parser.parse_args()
        try:
            check_software_switch(args.check_switch)
        except (AssertionError, OSError, subprocess.SubprocessError) as exc:
            parser.exit(1, 'LAB05 software-switch gate FAILED: ' + str(exc) + '\n')
        print('LAB05 software-switch object gate PASS (QEMU test still required)')
    else:
        unittest.main()
