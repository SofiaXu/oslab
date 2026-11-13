#!/usr/bin/env python3
"""Offline Minix-v1 (14-character names) image exchange, no mount/root required.

Only use on a STOPPED private QEMU disk. Supports the supplied partitioned
image and direct filesystem images. Does not implement fsck or other Minix
versions. Write operations take a nonblocking advisory lock shared by runner.
"""
import argparse
import fcntl
import functools
import os
from pathlib import Path
import stat
import struct
import time

BLOCK = 1024


def transactional(method):
    """Rollback a whole public operation, including nested directory updates."""
    @functools.wraps(method)
    def wrapped(self, *args, **kwargs):
        outer = self.undo is None
        if outer: self.undo = []
        try:
            result = method(self, *args, **kwargs)
        except BaseException:
            if outer:
                for offset, old in reversed(self.undo):
                    self.file.seek(offset); self.file.write(old)
            raise
        finally:
            if outer: self.undo = None
        return result
    return wrapped


class Minix:
    def __init__(self, path, writable=False):
        self.path = Path(path)
        self.file = self.path.open('r+b' if writable else 'rb')
        self.undo = None
        try:
            fcntl.flock(self.file, (fcntl.LOCK_EX if writable else fcntl.LOCK_SH) | fcntl.LOCK_NB)
            self.base = 0
            magic = struct.unpack('<H', self.read_at(1024 + 16, 2))[0]
            if magic != 0x137F:
                mbr = self.read_at(0, 512)
                if mbr[510:] != b'\x55\xaa':
                    raise ValueError('not a partitioned Minix-v1 image')
                self.base = struct.unpack_from('<I', mbr, 454)[0] * 512
            fields = struct.unpack('<6HIH', self.read_at(self.base + 1024, 18))
            self.ninodes, self.nzones, self.imaps, self.zmaps, self.first, shift, _, magic = fields
            if magic != 0x137F or shift != 0:
                raise ValueError('only Minix-v1, 14-char names, 1K zones supported')
            self.itable = 2 + self.imaps + self.zmaps
            minimum = self.itable + (self.ninodes*32+BLOCK-1)//BLOCK
            if (self.ninodes < 1 or self.imaps < 1 or self.zmaps < 1 or
                self.ninodes+1 > self.imaps*BLOCK*8 or
                self.nzones-self.first+1 > self.zmaps*BLOCK*8 or
                not minimum <= self.first < self.nzones or
                self.base+self.nzones*BLOCK > os.fstat(self.file.fileno()).st_size):
                raise ValueError('invalid Minix filesystem geometry')
            self.writable = writable
        except BaseException:
            self.file.close()
            raise

    def __enter__(self): return self
    def __exit__(self, *args): self.close()
    def close(self):
        if not self.file.closed:
            self.file.flush()
            if self.writable: os.fsync(self.file.fileno())
            self.file.close()

    def read_at(self, offset, size):
        self.file.seek(offset)
        data = self.file.read(size)
        if len(data) != size: raise ValueError('truncated filesystem image')
        return data

    def write_at(self, offset, data):
        if not self.writable: raise ValueError('read-only image')
        if offset < self.base or offset+len(data) > self.base+self.nzones*BLOCK:
            raise ValueError('write outside filesystem')
        if self.undo is not None: self.undo.append((offset,self.read_at(offset,len(data))))
        self.file.seek(offset)
        self.file.write(data)

    def block(self, n):
        if not 0 <= n < self.nzones: raise ValueError('zone out of bounds')
        return self.read_at(self.base + n * BLOCK, BLOCK)

    def setblock(self, n, data):
        if not self.first <= n < self.nzones or len(data) != BLOCK:
            raise ValueError('invalid data zone write')
        self.write_at(self.base + n * BLOCK, data)

    def inode(self, n):
        if not 1 <= n <= self.ninodes: raise ValueError('invalid inode')
        return list(struct.unpack('<HHIIBB9H', self.read_at(self.base + self.itable*BLOCK + (n-1)*32, 32)))

    def setinode(self, n, fields):
        self.write_at(self.base + self.itable*BLOCK + (n-1)*32, struct.pack('<HHIIBB9H', *fields))

    def bits(self, first, count, limit, reserve=0):
        for bit in range(reserve, limit):
            pos = self.base + first * BLOCK + bit//8
            value = self.read_at(pos, 1)[0]
            if not value & (1 << (bit%8)):
                self.write_at(pos, bytes([value | (1 << (bit%8))]))
                return bit
        raise ValueError('filesystem full')

    def alloc_inode(self): return self.bits(2, self.imaps, self.ninodes+1, 1)
    def alloc_zone(self):
        n = self.first - 1 + self.bits(2+self.imaps, self.zmaps, self.nzones-self.first+1, 1)
        self.setblock(n, bytes(BLOCK))
        return n

    def free_zone(self, n):
        if not self.first <= n < self.nzones: raise ValueError('invalid zone free')
        bit = n - self.first + 1
        pos = self.base + (2+self.imaps)*BLOCK + bit//8
        self.write_at(pos, bytes([self.read_at(pos, 1)[0] & ~(1 << (bit%8))]))

    def pointers(self, zone):
        return struct.unpack('<512H', self.block(zone)) if zone else (0,)*512

    def zones(self, inode):
        z = inode[6:]
        yield from z[:7]
        yield from self.pointers(z[7])
        if z[8]:
            for ptr in self.pointers(z[8]):
                yield from self.pointers(ptr)

    def read(self, n):
        inode = self.inode(n)
        remain = inode[2]
        data = bytearray()
        for z in self.zones(inode):
            if remain <= 0: break
            size = min(remain, BLOCK)
            data.extend(self.block(z)[:size] if z else bytes(size))
            remain -= size
        if remain: raise ValueError('file exceeds supported zone map')
        return bytes(data)

    def entries(self, n):
        if not stat.S_ISDIR(self.inode(n)[0]): raise ValueError('not a directory')
        data = self.read(n)
        for i in range(0, len(data), 16):
            ino = struct.unpack_from('<H', data, i)[0]
            if ino:
                yield data[i+2:i+16].split(b'\0')[0].decode('ascii'), ino

    def lookup(self, path):
        n = 1
        for part in Path(path).parts:
            if part in ('/', '.', ''): continue
            found = dict(self.entries(n)).get(part)
            if found is None: raise FileNotFoundError(path)
            n = found
        return n

    @transactional
    def replace(self, n, data):
        # Small teaching payloads: writing up to single-indirect range is enough.
        # Read and free existing double-indirect files correctly, never truncate silently.
        if len(data) > (7+512)*BLOCK: raise ValueError('write limited to 519 KiB')
        ino = self.inode(n)
        old = ino[6:]
        for z in self.zones(ino):
            if z: self.free_zone(z)
        if old[7]: self.free_zone(old[7])
        if old[8]:
            for z in self.pointers(old[8]):
                if z: self.free_zone(z)
            self.free_zone(old[8])
        ino[6:] = [0]*9
        indirect = [0]*512
        for i in range(0, len(data), BLOCK):
            z = self.alloc_zone()
            self.setblock(z, data[i:i+BLOCK].ljust(BLOCK, b'\0'))
            k = i//BLOCK
            if k < 7: ino[6+k] = z
            else:
                if not ino[13]: ino[13] = self.alloc_zone()
                indirect[k-7] = z
        if ino[13]: self.setblock(ino[13], struct.pack('<512H', *indirect))
        ino[2], ino[3] = len(data), int(time.time())
        self.setinode(n, ino)

    @transactional
    def create(self, path, mode=0o100644):
        path = Path(path)
        name = path.name.encode('ascii')
        if not name or len(name) > 14 or name in (b'.', b'..'):
            raise ValueError('Minix-v1 filename must contain 1..14 ASCII bytes')
        parent = self.lookup(str(path.parent))
        if path.name in dict(self.entries(parent)): raise FileExistsError(path)
        n = self.alloc_inode()
        self.setinode(n, [mode, 0, 0, int(time.time()), 0, 1]+[0]*9)
        data = self.read(parent)
        entry = struct.pack('<H14s', n, name)
        empty = next((i for i in range(0, len(data), 16) if data[i:i+2] == b'\0\0'), len(data))
        self.replace(parent, data[:empty] + entry + data[empty+16:])
        return n

    @transactional
    def mkdir(self, path):
        try:
            n = self.lookup(path)
            if not stat.S_ISDIR(self.inode(n)[0]): raise ValueError('not a directory')
            return n
        except FileNotFoundError: pass
        parent = self.lookup(str(Path(path).parent))
        n = self.create(path, 0o40755)
        self.replace(n, struct.pack('<H14sH14s', n, b'.', parent, b'..'))
        ino = self.inode(n); ino[5] = 2; self.setinode(n, ino)
        ino = self.inode(parent); ino[5] += 1; self.setinode(parent, ino)
        return n

    @transactional
    def put(self, path, data, mode=0o100644):
        try: n = self.lookup(path)
        except FileNotFoundError: n = self.create(path, mode)
        if not stat.S_ISREG(self.inode(n)[0]): raise ValueError('not a regular file')
        self.replace(n, data)
        ino = self.inode(n); ino[0] = mode; self.setinode(n, ino)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('image', type=Path)
    sub = ap.add_subparsers(dest='action', required=True)
    p = sub.add_parser('ls'); p.add_argument('path', nargs='?', default='/')
    p = sub.add_parser('get'); p.add_argument('guest'); p.add_argument('host', type=Path)
    p = sub.add_parser('put'); p.add_argument('host', type=Path); p.add_argument('guest'); p.add_argument('--mode', type=lambda s:int(s,8), default=0o644)
    p = sub.add_parser('mkdir'); p.add_argument('path')
    args = ap.parse_args()
    try:
        with Minix(args.image, args.action in ('put', 'mkdir')) as fs:
            if args.action == 'ls':
                for name, n in fs.entries(fs.lookup(args.path)):
                    ino = fs.inode(n); print(f'{n:5} {ino[0]:06o} {ino[2]:8} {name}')
            elif args.action == 'get': args.host.write_bytes(fs.read(fs.lookup(args.guest)))
            elif args.action == 'put': fs.put(args.guest, args.host.read_bytes(), 0o100000 | args.mode)
            else: fs.mkdir(args.path)
    except (OSError, ValueError) as exc:
        ap.exit(1, f'minix: {exc}\n')


if __name__ == '__main__': main()
