#!/usr/bin/env python3
"""Offline tool contracts; private scratch images only, never QEMU or live disks.

Run: python3 -m unittest discover -s tests -p test_tools.py -v
Cached-image cases skip without make prepare. Synthetic format/rollback cases
still run offline. Guest binaries are inspected and their startup ABI exercised
using an unprivileged i386 ELF harness, not a claimed Linux 0.11 boot test.
"""
import errno
import hashlib
from pathlib import Path
import platform
import shutil
import stat
import struct
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / 'tools'
sys.path.insert(0, str(TOOLS))
from minix import Minix
from guest_build import build
import oslab

BLOCK = 1024


def command(args, **kw):
    result = subprocess.run(list(map(str, args)), stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, timeout=60, **kw)
    if result.returncode:
        raise AssertionError(f'{args!r}: exit {result.returncode}\n' +
                             result.stdout.decode(errors='replace'))
    return result.stdout


def fixture(path, zones=64, payload=None):
    """Independent on-disk Minix-v1 fixture, with optional double-indirect file.

    32 inodes, one bitmap each, root inode 1 in block 4, first data zone 5.
    Build bytes directly: constructing test data must not use the writer tested.
    """
    image = bytearray(zones * BLOCK)
    struct.pack_into('<6HIH', image, BLOCK, 32, zones, 1, 1, 5, 0,
                     (7 + 512 + 512*512)*BLOCK, 0x137f)
    image[2*BLOCK] = 3  # reserved inode 0, root inode 1
    image[3*BLOCK] = 3  # reserved bit 0, root zone 5
    entries = [(1, b'.'), (1, b'..')]
    next_zone = 6

    def allocate(content):
        nonlocal next_zone
        z = next_zone
        next_zone += 1
        if z >= zones:
            raise ValueError('fixture too small')
        image[z*BLOCK:z*BLOCK+len(content)] = content
        bit = z - 5 + 1
        image[3*BLOCK + bit//8] |= 1 << (bit % 8)
        return z

    if payload is not None:
        image[2*BLOCK] |= 4
        entries.append((2, b'payload'))
        pointers = [allocate(payload[i:i+BLOCK])
                    for i in range(0, len(payload), BLOCK)]
        inode_zones = pointers[:7] + [0] * (9 - min(7, len(pointers)))
        if len(pointers) > 7:
            inode_zones[7] = allocate(struct.pack('<512H',
                *(pointers[7:519] + [0]*max(0, 519-len(pointers)))))
        if len(pointers) > 519:
            groups = []
            for i in range(519, len(pointers), 512):
                group = pointers[i:i+512]
                groups.append(allocate(struct.pack('<512H', *(group+[0]*(512-len(group))))))
            inode_zones[8] = allocate(struct.pack('<512H', *(groups+[0]*(512-len(groups)))))
        struct.pack_into('<HHIIBB9H', image, 4*BLOCK+32,
                         0o100644, 0, len(payload), 0, 0, 1, *inode_zones)
    directory = b''.join(struct.pack('<H14s', ino, name) for ino, name in entries)
    image[5*BLOCK:5*BLOCK+len(directory)] = directory
    struct.pack_into('<HHIIBB9H', image, 4*BLOCK,
                     0o40755, 0, len(directory), 0, 0, 2, 5, *([0]*8))
    path.write_bytes(image)


class Scratch(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='oslab-tools-test-')
        self.addCleanup(self.temp.cleanup)
        self.scratch = Path(self.temp.name)
        self.disk = self.scratch / 'disk.img'


class CachedImageTests(Scratch):
    def setUp(self):
        super().setUp()
        cache = ROOT / '.cache/hdc-0.11.img'
        if not cache.is_file():
            self.skipTest('rootfs cache absent; run make prepare for real-image tests')
        shutil.copyfile(cache, self.disk)

    def test_root_shell_get_and_single_indirect(self):
        with Minix(self.disk) as fs:
            root = dict(fs.entries(1))
            self.assertTrue({'bin', 'etc', 'usr'} <= root.keys())
            ino = fs.inode(fs.lookup('/bin/sh'))
            self.assertTrue(stat.S_ISREG(ino[0]))
            self.assertGreater(ino[2], 7*BLOCK)
            self.assertNotEqual(ino[13], 0, 'shell must exercise single-indirect reads')
            expected = fs.read(fs.lookup('/bin/sh'))
            self.assertEqual(len(expected), ino[2])
            self.assertEqual(hashlib.sha256(expected).hexdigest(),
                '3ffd73fa97234a965a996e4c3d0c839887eeb2f077f56d1150bf6fe0d10a2021',
                'known /bin/sh from the pinned rootfs')
        output = self.scratch / 'shell'
        command([sys.executable, TOOLS/'minix.py', self.disk, 'get', '/bin/sh', output])
        self.assertEqual(output.read_bytes(), expected)

    def test_create_replace_shrink_reuse_and_preserve_directories(self):
        with Minix(self.disk, True) as fs:
            root_before = dict(fs.entries(1))
            bin_before = dict(fs.entries(fs.lookup('/bin')))
            shell_before = fs.read(fs.lookup('/bin/sh'))
            fs.mkdir('/tooltest')
            parent = fs.lookup('/tooltest')
            child = fs.mkdir('/tooltest/child')
            self.assertEqual(dict(fs.entries(child)), {'.': child, '..': parent})
            self.assertEqual(fs.mkdir('/tooltest/child'), child)
            # Grow the directory across a block boundary; replacing its blocks
            # must preserve all earlier entries and unrelated directories.
            for i in range(70):
                fs.put('/tooltest/f%03d' % i, bytes([i])*17)
            payload = bytes(range(256))*65 + b'end'
            for data in (payload, b'short', b'', payload, b'last'):
                fs.put('/tooltest/child/file', data, 0o100755)
                self.assertEqual(fs.read(fs.lookup('/tooltest/child/file')), data)
            self.assertEqual(fs.inode(fs.lookup('/tooltest/child/file'))[0], 0o100755)
            for i in range(70):
                self.assertEqual(fs.read(fs.lookup('/tooltest/f%03d' % i)), bytes([i])*17)
            self.assertEqual(dict(fs.entries(fs.lookup('/bin'))), bin_before)
            self.assertEqual(fs.read(fs.lookup('/bin/sh')), shell_before)
            self.assertEqual({k:v for k,v in fs.entries(1) if k != 'tooltest'}, root_before)
            bitmap_before = fs.read_at(fs.base+(2+fs.imaps)*BLOCK, fs.zmaps*BLOCK)
            for _ in range(12):
                fs.put('/tooltest/child/file', payload)
                fs.put('/tooltest/child/file', b'last')
            self.assertEqual(fs.read_at(fs.base+(2+fs.imaps)*BLOCK, fs.zmaps*BLOCK),
                             bitmap_before, 'shrinking replacements must reclaim blocks')
        with Minix(self.disk) as fs:
            self.assertEqual(fs.read(fs.lookup('/tooltest/child/file')), b'last')
            self.assertEqual(fs.read(fs.lookup('/bin/sh')), shell_before)

    def test_existing_double_indirect_file_if_available(self):
        with Minix(self.disk) as fs:
            def walk(n, seen):
                if n in seen:
                    return
                seen.add(n)
                for name, child in fs.entries(n):
                    if name in ('.', '..'):
                        continue
                    ino = fs.inode(child)
                    if stat.S_ISDIR(ino[0]):
                        yield from walk(child, seen)
                    elif stat.S_ISREG(ino[0]) and ino[2] > 519*BLOCK:
                        yield child, ino
            found = next(walk(1, set()), None)
            if found is None:
                self.skipTest('pinned rootfs contains no regular file >519 KiB; synthetic case covers it')
            n, ino = found
            self.assertNotEqual(ino[14], 0)
            self.assertEqual(len(fs.read(n)), ino[2])

    def test_cli_mkdir_put_get(self):
        data = b'\x00\xffguest exchange\n' * 1300
        source, output = self.scratch/'input', self.scratch/'output'
        source.write_bytes(data)
        command([sys.executable, TOOLS/'minix.py', self.disk, 'mkdir', '/exchange'])
        command([sys.executable, TOOLS/'minix.py', self.disk, 'put', source,
                 '/exchange/input', '--mode', '755'])
        command([sys.executable, TOOLS/'minix.py', self.disk, 'get', '/exchange/input', output])
        self.assertEqual(output.read_bytes(), data)
        with Minix(self.disk) as fs:
            self.assertEqual(fs.inode(fs.lookup('/exchange/input'))[0], 0o100755)


class MinixSafetyTests(Scratch):
    def setUp(self):
        super().setUp()
        fixture(self.disk)

    def assert_unchanged_after_failure(self, operation):
        before = self.disk.read_bytes()
        with Minix(self.disk, True) as fs:
            with self.assertRaises((ValueError, OSError)):
                operation(fs)
        self.assertEqual(self.disk.read_bytes(), before,
                         'failed public operations must roll back inode, directory, bitmap and data')

    def test_enospc_replacement_rolls_back_existing_contents(self):
        with Minix(self.disk, True) as fs:
            fs.put('/keep', b'original'*200)
        self.assert_unchanged_after_failure(lambda fs: fs.put('/keep', b'x'*(80*BLOCK)))
        with Minix(self.disk) as fs:
            self.assertEqual(fs.read(fs.lookup('/keep')), b'original'*200)

    def test_failed_new_file_rolls_back_parent_and_inode(self):
        self.assert_unchanged_after_failure(lambda fs: fs.put('/new', b'x'*(80*BLOCK)))
        with Minix(self.disk, True) as fs:
            fs.put('/small', b'works after rollback')
            self.assertEqual(fs.read(fs.lookup('/small')), b'works after rollback')
            self.assertNotIn('new', dict(fs.entries(1)))

    def test_failed_mkdir_rolls_back_nested_parent_change(self):
        # Leave no free data zone: create first updates the parent directory,
        # then mkdir fails when allocating its own '.'/'..' directory data.
        with Minix(self.disk, True) as fs:
            fs.put('/filler', b'x'*(57*BLOCK))  # root + 57 data + indirect = all 59 zones
        self.assert_unchanged_after_failure(lambda fs: fs.mkdir('/newdir'))

    def test_rejected_names_types_and_oversized_write_do_not_mutate(self):
        with Minix(self.disk, True) as fs:
            fs.put('/abcdefghijklmn', b'14-byte name')
            fs.mkdir('/dir')
        for path in ('/abcdefghijklmno', '/non-ascii-é'):
            with self.subTest(path=path):
                self.assert_unchanged_after_failure(lambda fs: fs.put(path, b'bad'))
        self.assert_unchanged_after_failure(lambda fs: fs.put('/dir', b'not a file'))
        self.assert_unchanged_after_failure(lambda fs: fs.mkdir('/abcdefghijklmn'))
        self.assert_unchanged_after_failure(lambda fs: fs.put('/too-big', b'x'*(519*BLOCK+1)))

    def test_double_indirect_read_shrink_and_reclaim(self):
        data = bytes(range(251))*((523*BLOCK)//251+1)
        data = data[:523*BLOCK-19]
        fixture(self.disk, zones=600, payload=data)
        with Minix(self.disk, True) as fs:
            self.assertEqual(fs.read(fs.lookup('/payload')), data)
            fs.put('/payload', b'shrunk')
            # Enough payloads to require recycling the released double-indirect
            # data and pointer blocks, rather than merely forgetting them.
            fs.put('/large', b'y'*(519*BLOCK))
            fs.put('/tail', b'z'*(70*BLOCK))
            self.assertEqual(fs.read(fs.lookup('/payload')), b'shrunk')
            self.assertEqual(fs.read(fs.lookup('/large')), b'y'*(519*BLOCK))
            self.assertEqual(fs.read(fs.lookup('/tail')), b'z'*(70*BLOCK))

    def test_shared_readers_exclusive_writer_and_external_runner_lock(self):
        with Minix(self.disk):
            with Minix(self.disk):
                pass
            with self.assertRaises(BlockingIOError):
                Minix(self.disk, True)
        with Minix(self.disk, True):
            for writable in (False, True):
                with self.subTest(writable=writable), self.assertRaises(BlockingIOError):
                    Minix(self.disk, writable)
        # Independent process emulates the runner's flock contract, no QEMU.
        script = ('import fcntl,sys; f=open(sys.argv[1],"r+b"); '
                  'fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB); '
                  'print("LOCKED",flush=True); sys.stdin.readline()')
        proc = subprocess.Popen([sys.executable, '-c', script, str(self.disk)],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True)
        try:
            self.assertEqual(proc.stdout.readline().strip(), 'LOCKED')
            with self.assertRaises(BlockingIOError):
                Minix(self.disk)
            with self.assertRaises(BlockingIOError):
                Minix(self.disk, True)
        finally:
            proc.communicate('\n', timeout=10)
        self.assertEqual(proc.returncode, 0)
        with Minix(self.disk, True):
            pass  # failed lock attempts must not retain a lock

    def test_read_only_write_rejected_and_lock_released_on_exception(self):
        before = self.disk.read_bytes()
        with self.assertRaisesRegex(RuntimeError, 'exit body'):
            with Minix(self.disk) as fs:
                with self.assertRaises(ValueError):
                    fs.put('/forbidden', b'data')
                raise RuntimeError('exit body')
        self.assertEqual(self.disk.read_bytes(), before)
        with Minix(self.disk, True):
            pass

    def test_malformed_images_rejected_without_writes_or_lock_leaks(self):
        valid = self.disk.read_bytes()
        bad_images = {'empty': b'', 'truncated': valid[:1030], 'nonsense': b'\0'*4096}
        # Mutate documented superblock fields rather than tool internals.
        for name, offset, value in (('no-inodes', 0, 0), ('no-imap', 4, 0),
                                    ('no-zmap', 6, 0), ('metadata-overlap', 8, 4),
                                    ('extent-past-eof', 2, 800), ('wrong-magic', 16, 0x138f),
                                    ('unsupported-shift', 10, 1), ('imap-too-small', 0, 9000)):
            bad = bytearray(valid)
            struct.pack_into('<H', bad, BLOCK+offset, value)
            bad_images[name] = bytes(bad)
        bad = bytearray(4096)
        bad[510:512] = b'\x55\xaa'
        struct.pack_into('<I', bad, 454, 0xfffffff0)
        bad_images['mbr-offset-past-eof'] = bytes(bad)
        for name, data in bad_images.items():
            with self.subTest(name=name):
                self.disk.write_bytes(data)
                with self.assertRaises((ValueError, OSError)):
                    Minix(self.disk, True)
                self.assertEqual(self.disk.read_bytes(), data)
                # Direct OS lock ensures constructor failure closed its file.
                import fcntl
                with self.disk.open('r+b') as handle:
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)


class GuestBuildTests(Scratch):
    def setUp(self):
        super().setUp()
        for tool in ('gcc', 'ld', 'objcopy', 'nm'):
            if not shutil.which(tool):
                self.skipTest('guest compile tests need apt build-essential binutils: '+tool)
        self.source = self.scratch/'program.c'
        self.source.write_text(r'''
volatile unsigned int initialized = 0x12345678;
volatile unsigned char zeroed[8193];
int same(const char *a, const char *b) {
    while (*a && *a == *b) { a++; b++; } return *a == *b;
}
int main(int argc, char **argv, char **envp) {
    if (argc != 3 || !same(argv[0], "guest") || !same(argv[1], "alpha") ||
        !same(argv[2], "two words") || argv[3] != 0) return 11;
    if (!envp || !same(envp[0], "MODE=abi") || envp[1] != 0) return 12;
    if (initialized != 0x12345678 || zeroed[0] || zeroed[8192]) return 13;
    zeroed[8192] = 7;
    return 37;
}
''')
        self.output = self.scratch/'program'
        build(self.source, self.output)

    def test_zmagic_text_data_bss_entry_and_debug_symbols(self):
        data = self.output.read_bytes()
        magic, text, initialized, bss, syms, entry, tr, dr = struct.unpack_from('<8I', data)
        self.assertEqual(magic, 0o413)
        self.assertEqual(entry, 0)
        self.assertEqual((syms, tr, dr), (0, 0, 0))
        self.assertGreater(text, 0)
        self.assertEqual(text % 4096, 0)
        self.assertGreaterEqual(initialized, 4)
        self.assertGreaterEqual(bss, 8193)
        self.assertEqual(data[32:1024], bytes(992))
        self.assertEqual(len(data), 1024+text+initialized, 'BSS must not occupy file payload')
        # Compare actual ELF section bytes/addresses, independently of builder's nm arithmetic.
        elf = self.output.with_suffix('.elf').read_bytes()
        self.assertEqual(elf[:7], b'\x7fELF\x01\x01\x01')
        self.assertEqual(struct.unpack_from('<H', elf, 18)[0], 3)  # EM_386
        shoff = struct.unpack_from('<I', elf, 32)[0]
        shentsize, shnum, shstrndx = struct.unpack_from('<3H', elf, 46)
        sections = [struct.unpack_from('<10I', elf, shoff+i*shentsize) for i in range(shnum)]
        names_section = sections[shstrndx]
        strings = elf[names_section[4]:names_section[4]+names_section[5]]
        named = {strings[s[0]:].split(b'\0', 1)[0].decode(): s for s in sections}
        self.assertIn('.debug_info', named, 'retained ELF must carry usable debug information')
        for name in ('.text', '.data'):
            section = named[name]
            address, offset, size = section[3:6]
            self.assertEqual(data[1024+address:1024+address+size], elf[offset:offset+size])
        self.assertEqual(named['.data'][3], text)
        self.assertEqual(named['.bss'][1], 8)  # SHT_NOBITS
        self.assertEqual(named['.bss'][3]+named['.bss'][5], text+initialized+bss)
        symbols = command(['nm', '-n', self.output.with_suffix('.elf')]).decode()
        for name in ('_start', 'main', 'initialized', 'zeroed'):
            self.assertRegex(symbols, r'(?m)^[0-9a-f]+ [A-Za-z] '+name+r'$')

    def test_actual_startup_passes_legacy_argc_argv_envp_and_exit_code(self):
        if platform.machine() not in ('x86_64', 'i386', 'i686'):
            self.skipTest('startup execution harness requires host IA32 support')
        harness = self.scratch/'harness.S'
        harness.write_text(r'''
.section .data
arg0: .asciz "guest"
arg1: .asciz "alpha"
arg2: .asciz "two words"
env0: .asciz "MODE=abi"
.align 4
args: .long arg0, arg1, arg2, 0
envs: .long env0, 0
.section .text
.globl harness
harness:
    pushl $envs
    pushl $args
    pushl $3
    jmp _start
.section .note.GNU-stack,"",@progbits
''')
        obj = self.scratch/'harness.o'
        command(['gcc', '-m32', '-c', harness, '-o', obj])
        objects = self.output.parent/(self.output.name+'.objects')
        executable = self.scratch/'abi-harness'
        command(['ld', '-m', 'elf_i386', '-e', 'harness', '-o', executable,
                 obj, objects/'start.o', objects/'libc.o', objects/'main.o'])
        try:
            result = subprocess.run([str(executable)], stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, timeout=10)
        except OSError as exc:
            if exc.errno == errno.ENOEXEC:
                self.skipTest('host does not support IA32 execution; format checks still run')
            raise
        self.assertEqual(result.returncode, 37,
                         'actual guest startup must pass old exec ABI and return main status to _exit')


class KernelWorkspaceTests(Scratch):
    def setUp(self):
        super().setUp()
        # Only the layout contract is needed; no real kernel, compiler, disk,
        # patches, or student sources are touched by workspace sync tests.
        self.repo = self.scratch/'repository'
        vendor = self.repo/'vendor/linux-0.11/kernel'
        vendor.mkdir(parents=True)
        (vendor/'sched.c').write_text('/* untouched vendor source */\n')
        self.overlay = self.repo/'labs/lab01/student/kernel/who.c'
        self.overlay.parent.mkdir(parents=True)
        self.original = '/* original student overlay */\n'
        self.overlay.write_text(self.original)
        root_patch = patch.object(oslab, 'ROOT', self.repo)
        root_patch.start()
        self.addCleanup(root_patch.stop)
        self.kernel = oslab.kernel_workspace(1, 'student')
        self.target = self.kernel/'kernel/who.c'
        self.assertEqual(self.target.read_text(), self.original)

    def test_repeated_overlay_preserves_student_workspace_edits(self):
        edited = '/* student work must survive another make lab1 */\n'
        self.target.write_text(edited)
        unrelated = self.kernel/'kernel/my_work.c'
        unrelated.write_text('/* new student file */\n')
        for _ in range(2):
            self.assertEqual(oslab.kernel_workspace(1, 'student'), self.kernel)
            self.assertEqual(self.target.read_text(), edited)
            self.assertEqual(unrelated.read_text(), '/* new student file */\n')
        self.assertEqual(self.overlay.read_text(), self.original)
        self.assertEqual((self.kernel/'kernel/sched.c').read_text(),
                         '/* untouched vendor source */\n')

    def test_both_changed_fail_clearly_without_overwriting_either(self):
        student_edit = '/* independently edited workspace */\n'
        updated_overlay = '/* updated teaching scaffold */\n'
        self.target.write_text(student_edit)
        self.overlay.write_text(updated_overlay)
        manifest = self.kernel.parent/'overlay-state.json'
        before_manifest = manifest.read_bytes()
        for _ in range(2):
            with self.assertRaisesRegex(ValueError, 'Both overlay and workspace changed') as raised:
                oslab.kernel_workspace(1, 'student')
            self.assertIn(str(self.overlay), str(raised.exception))
            self.assertIn(str(self.target), str(raised.exception))
            self.assertEqual(self.target.read_text(), student_edit)
            self.assertEqual(self.overlay.read_text(), updated_overlay)
            self.assertEqual(manifest.read_bytes(), before_manifest,
                             'failed reconciliation must not mark new overlay applied')

    def test_new_overlay_syncs_when_workspace_was_unchanged(self):
        updated = '/* revised scaffold, safe to sync */\n'
        self.overlay.write_text(updated)
        self.assertEqual(oslab.kernel_workspace(1, 'student'), self.kernel)
        self.assertEqual(self.target.read_text(), updated)
        self.assertEqual(self.overlay.read_text(), updated)
        # After accepting the update, later edits are protected by its new
        # baseline too, rather than comparing forever with the first version.
        self.target.write_text('/* work on revised scaffold */\n')
        oslab.kernel_workspace(1, 'student')
        self.assertEqual(self.target.read_text(), '/* work on revised scaffold */\n')


class StudentDistributionTests(Scratch):
    def test_real_student_sources_present_and_private_artifacts_excluded(self):
        # Stage a source snapshot so packaging never touches dist/ or races
        # main's active kernel build. The packager itself runs unmodified.
        stage = self.scratch/'repository'
        excluded = {'.git', '.tmp', '.cache', 'build', 'dist', '__pycache__'}
        shutil.copytree(ROOT, stage, ignore=lambda directory, names: [n for n in names if n in excluded])
        for directory in ('.git', '.tmp', '.cache', 'build', 'dist', '__pycache__',
                          'labs/lab01/reference', 'nested/reference', 'nested/build',
                          'vendor/patches'):
            target = stage/directory/'DO_NOT_DISTRIBUTE'
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text('private fixture')
        (stage/'nested/cache.pyc').write_bytes(b'compiled code')
        with patch.object(oslab, 'ROOT', stage):
            oslab.student_dist()
        with tarfile.open(stage/'dist/oslab-student.tar.gz') as archive:
            members = archive.getmembers()
            names = {m.name for m in members}
            self.assertTrue(names)
            forbidden = excluded | {'reference'}
            for member in members:
                rel = Path(member.name)
                self.assertFalse(rel.is_absolute())
                self.assertNotIn('..', rel.parts)
                self.assertEqual(rel.parts[0], 'oslab-student')
                self.assertFalse(forbidden.intersection(rel.parts))
                self.assertNotEqual(rel.suffix, '.pyc')
                self.assertNotIn('DO_NOT_DISTRIBUTE', member.name)
                self.assertTrue(member.isfile(), 'source distribution must contain regular files')
            # Match every actual student source, including kernel overlays;
            # merely archiving an empty student/ directory is not sufficient.
            students = [p for p in (stage/'labs').rglob('*') if p.is_file() and
                        'student' in p.relative_to(stage).parts]
            self.assertGreater(len(students), 8)
            required = students + [stage/'README.md', stage/'Makefile',
                                   stage/'tools/minix.py', stage/'tools/guest_build.py',
                                   stage/'docs/lab05.md', stage/'docs/lab08.md']
            for source in required:
                name = 'oslab-student/'+source.relative_to(stage).as_posix()
                self.assertIn(name, names)
                self.assertEqual(archive.extractfile(name).read(), source.read_bytes())


if __name__ == '__main__':
    unittest.main()
