#!/usr/bin/env python3
"""Shared, explicit student/reference entry points. Python standard library only."""
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request

from guest_build import build as guest_build
from minix import Minix
from qemu import Machine

ROOT = Path(__file__).resolve().parents[1]
KERNEL_LABS = {1, 3, 5, 9}  # 9 is lab 2's optional kernel extension.
LABEL = {1:'lab01', 2:'lab02', 3:'lab03', 4:'lab04', 5:'lab05', 6:'lab06', 7:'lab07', 8:'lab08', 9:'lab02-kernel'}


def run(cmd, **kwargs):
    return subprocess.run(list(map(str, cmd)), check=True, cwd=ROOT, **kwargs)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()


@contextmanager
def exclusive_lock(path, wait=False):
    path = Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a') as lock:
        try: fcntl.flock(lock,fcntl.LOCK_EX | (0 if wait else fcntl.LOCK_NB))
        except BlockingIOError: raise ValueError('another command is using '+str(path.parent)+'; stop it before rebuilding or retry later')
        yield


def prepare():
    with exclusive_lock(ROOT/'.cache/prepare.lock', wait=True):
        return prepare_locked()


def prepare_locked():
    meta = json.loads((ROOT/'vendor/sources.json').read_text())['rootfs']
    cache = ROOT/'.cache/hdc-0.11.img'
    cache.parent.mkdir(exist_ok=True)
    if cache.exists() and digest(cache) == meta['sha256']:
        print('rootfs cache: SHA-256 verified'); return cache
    if cache.exists():
        raise ValueError('rootfs cache checksum mismatch; preserve/rename it, then retry make prepare')
    print('Downloading pinned rootfs (about 60 MiB); no privileged mount required.', flush=True)
    tmp = cache.with_suffix('.download')
    try:
        with urllib.request.urlopen(meta['url'], timeout=60) as src, tmp.open('wb') as dst:
            shutil.copyfileobj(src, dst)
        if tmp.stat().st_size != meta['bytes'] or digest(tmp) != meta['sha256']:
            raise ValueError('download checksum/size mismatch')
        tmp.chmod(0o444)
        tmp.replace(cache)
    finally:
        tmp.unlink(missing_ok=True)
    print('rootfs downloaded and SHA-256 verified')
    return cache


def doctor():
    needed = ['gcc','as','ld','make','patch','objcopy','nm','gdb','qemu-system-i386','python3','curl','git','xz']
    missing = [name for name in needed if not shutil.which(name)]
    print('Host:', platform.system(), platform.machine())
    release = Path('/etc/os-release').read_text() if Path('/etc/os-release').exists() else ''
    print(next((s for s in release.splitlines() if s.startswith('PRETTY_NAME=')), 'Unknown distribution'))
    for name in needed: print(f'{name}: {shutil.which(name) or "MISSING"}')
    if platform.machine() != 'x86_64': missing.append('x86_64 host (required baseline)')
    if shutil.which('gcc'):
        p = subprocess.run(['gcc','-m32','-march=i386','-x','c','-c','-o',os.devnull,'-'], input='int x;\n', text=True, capture_output=True)
        print('GCC i386 object:', 'OK' if p.returncode == 0 else 'FAILED')
        if p.returncode: missing.append('GCC i386 code generation')
    print('WSLg graphical display:', 'detected' if os.getenv('DISPLAY') or os.getenv('WAYLAND_DISPLAY') else 'not detected; QEMU_DISPLAY=curses or headless checks available')
    print('apt: sudo apt install build-essential gcc-multilib binutils gdb qemu-system-x86 qemu-system-gui python3 git curl xz-utils patch')
    if missing: raise ValueError('missing requirements: '+', '.join(missing))
    print('Environment checks passed. QEMU execution is verified separately by check-labN.')


def workdir(n, impl): return ROOT/'build'/LABEL[n]/impl


def kernel_workspace(n, impl):
    lab = ROOT/'labs'/LABEL[n]
    base = workdir(n, impl)
    kernel = base/'kernel'
    manifest = base/'overlay-state.json'
    if not kernel.exists():
        base.mkdir(parents=True,exist_ok=True)
        # Work on a new tree first; a failed patch must never leave a partial workspace.
        temp = Path(tempfile.mkdtemp(prefix='kernel-new-',dir=base))
        try:
            shutil.copytree(ROOT/'vendor/linux-0.11', temp, dirs_exist_ok=True)
            patch = lab/impl/'kernel.patch'
            if not patch.exists(): patch = lab/'kernel.patch'
            if patch.exists():
                with (base/'patch.log').open('w') as log:
                    run(['patch','--batch','-p1','-d',temp,'-i',patch],stdout=log,stderr=subprocess.STDOUT)
            temp.rename(kernel)
        finally:
            if temp.exists(): shutil.rmtree(temp)
    state = json.loads(manifest.read_text()) if manifest.exists() else {}
    overlay = lab/impl/'kernel'
    for source in sorted(overlay.rglob('*')):
        if not source.is_file(): continue
        rel = str(source.relative_to(overlay))
        target = kernel/'kernel'/rel
        sha = digest(source)
        previous = state.get(rel)
        if previous is None or previous != sha:
            if previous is not None and target.exists() and digest(target) != previous:
                raise ValueError(f'Both overlay and workspace changed: {source} and {target}; reconcile manually (nothing overwritten)')
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(source,target)
            state[rel] = sha
    manifest.write_text(json.dumps(state,indent=2)+'\n')
    return kernel


def build_kernel(n, impl):
    cache = prepare()
    base, lab = workdir(n,impl), ROOT/'labs'/LABEL[n]
    kernel = kernel_workspace(n,impl)
    # Upstream top-level make does not propagate changed sources to submakes.
    # Always rebuild artifacts, while preserving every source and the guest disk.
    print(f'Building {LABEL[n]} {impl}: {kernel}',flush=True)
    with (base/'build.log').open('w') as log:
        try:
            run(['make','-C',kernel,'clean'],stdout=log,stderr=subprocess.STDOUT)
            run(['make','-C',kernel],stdout=log,stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError:
            raise ValueError('kernel build failed; inspect '+str(base/'build.log'))
    sources = {p.stem:p for p in (lab/'guest').glob('*.c')}
    sources.update({p.stem:p for p in (lab/impl/'guest').glob('*.c')})
    if (lab/'guest_test.c').exists(): sources['lab05_test'] = lab/'guest_test.c'
    disk = base/'rootfs.img'
    if not disk.exists(): shutil.copyfile(cache,disk)
    binaries = {}
    for name, source in sorted(sources.items()):
        binaries[name] = guest_build(source,base/'guest'/name)
    with Minix(disk,True) as fs:
        fs.mkdir('/lab'); fs.mkdir('/var')
        for name, path in binaries.items(): fs.put('/lab/'+name,path.read_bytes(),0o100755)
    print('Guest binaries:', ', '.join('/lab/'+s for s in binaries))
    print('Private disk:',disk)
    return base


def build(n, impl):
    if not (ROOT/'labs'/LABEL[n]/impl).is_dir():
        raise ValueError(f'{LABEL[n]}: {impl} implementation is absent (student packages intentionally omit reference answers)')
    if n in KERNEL_LABS: return build_kernel(n,impl)
    base = workdir(n,impl)
    run(['make','--no-print-directory','-C',ROOT/'labs'/LABEL[n],f'IMPL={impl}',f'BUILD_DIR={base}'])
    return base


def guest_commands(n, quantum=15):
    if n == 1: return ['/lab/lab01_test']
    if n == 3: return ['/lab/process '+str(quantum)]
    if n == 5: return ['/lab/lab05_test','/lab/lab05_test 12 120000']
    return ['/lab/sem_test','/lab/pc 2 500','/lab/pc 5 997']


def check_kernel_once(n, impl, base, quantum=15):
    label = LABEL[n]
    # Checks never modify a student's interactive disk or overwrite its work.
    disk = base/f'check-{quantum}.img'
    shutil.copyfile(prepare(),disk)
    with Minix(base/'rootfs.img') as source, Minix(disk,True) as target:
        target.mkdir('/lab'); target.mkdir('/var')
        for name, ino in source.entries(source.lookup('/lab')):
            if name not in ('.','..'): target.put('/lab/'+name,source.read(ino),0o100755)
        commands = guest_commands(n,quantum)
        script = 'echo CHECK_BEGIN > /var/check.result\n'
        for command in commands:
            script += command+' >> /var/check.result 2>&1\necho EXIT:$? >> /var/check.result\n'
        script += 'sync\necho OSLAB_CHECK_DONE\n'
        target.put('/etc/rc',script.encode(),0o100644)
    screen_path = base/f'screen-{quantum}.txt'
    try:
        with Machine(base/'kernel/Image',disk,log=base/f'qemu-{quantum}.log') as q:
            try: screen = q.wait_for('OSLAB_CHECK_DONE',timeout=90)
            except BaseException:
                screen_path.write_text(q.screen()); raise
            screen_path.write_text(screen)
            # Check that boot also reaches an interactive shell after /etc/rc.
            q.wait_for('[/usr/root]#',timeout=15)
    finally:
        # Closed QEMU flushes the image before offline inspection.
        pass
    with Minix(disk) as fs:
        result = fs.read(fs.lookup('/var/check.result')).decode('ascii',errors='replace')
        (base/f'result-{quantum}.txt').write_text(result)
    if n==9:
        print('Kernel semaphore/PC transcript saved:',base/f'result-{quantum}.txt')
        print('\n'.join(line for line in result.splitlines() if 'PASS' in line or line.startswith('EXIT:')))
    else: print(result,end='')
    markers = {1:['LAB01 PASS'],3:['LAB03 PASS'],5:['LAB05_PASS'],9:['LAB02-KERNEL PASS','LAB02-PC PASS']}[n]
    if any(marker not in result for marker in markers) or re.findall(r'^EXIT:(\d+)$',result,re.M) != ['0']*len(guest_commands(n)):
        raise ValueError(f'{label} {impl}: guest acceptance failed; see {base}/result-{quantum}.txt')
    if n==9:
        values = [int(v) for v in re.findall(r'^\d+:\s*(\d+)$',result,re.M)]
        if values != list(range(501))+list(range(998)):
            raise ValueError('kernel PC output contains missing, duplicate or unordered values')
    if n==3:
        log = base/f'process-{quantum}.log'
        with Minix(disk) as fs:
            try: log.write_bytes(fs.read(fs.lookup('/var/process.log')))
            except FileNotFoundError:
                raise ValueError('lab03: workload did not create /var/process.log; see '+str(base/f'result-{quantum}.txt'))
        match = re.search(r'^SELECTED((?: \d+)+)$',result,re.M)
        if not match: raise ValueError('missing workload PID list')
        with (base/f'stats-{quantum}.json').open('w') as f:
            run(['python3',ROOT/'tools/trace_stats.py',log,'--pids',*match.group(1).split(),'--json'],stdout=f)
        text = log.read_text()
        if not all('\t'+state+'\t' in text for state in 'NJRWE'):
            raise ValueError('real kernel log is missing a required state')


def check(n, impl):
    base = build(n,impl)
    if n in KERNEL_LABS:
        if n==5 and 'TODO_LAB5_SOFTWARE_SWITCH' in (base/'kernel/kernel/lab5_switch.S').read_text():
            raise ValueError('INCOMPLETE: lab5 still uses the hardware-switch scaffold; complete AI-assisted software switching first')
        if n==5:
            disassembly = subprocess.check_output(['objdump','-dr',str(base/'kernel/kernel/lab5_switch.o')],text=True)
            if re.search(r'\b(ljmp|lcall|ltr)\b',disassembly):
                raise ValueError('INCOMPLETE: lab5 object still contains hardware task switching (ljmp/lcall/ltr)')
            if not re.search(r'\blldt\b',disassembly):
                raise ValueError('INCOMPLETE: lab5 switch object does not load the next LDT')
        for quantum in ([15,5] if n==3 else [15]): check_kernel_once(n,impl,base,quantum)
        print(f'{LABEL[n]} {impl}: real QEMU acceptance passed')
    elif n==2:
        env=dict(os.environ,PC=str(base/'pc'))
        run(['python3',ROOT/'tests/test_pc.py','-v'],env=env)
    else:
        env=dict(os.environ,OSLAB_IMPL=impl,OSLAB_LAB=str(n),OSLAB_BUILD_DIR=str(base))
        run(['python3',ROOT/'tests/test_algorithms.py','-v'],env=env)


def launch(n, impl, display='gtk', debug=False, args=''):
    base = build(n,impl)
    if n in KERNEL_LABS:
        if display=='gtk' and not (os.getenv('DISPLAY') or os.getenv('WAYLAND_DISPLAY')):
            raise ValueError('WSLg display not detected; see docs/setup-wsl2.md or use QEMU_DISPLAY=curses')
        print('Linux 0.11 guest: binaries in /lab; Ctrl+Alt+G releases pointer. Close window to stop.',flush=True)
        if debug: print('GDB listening only at 127.0.0.1:1234; CPU paused. Use '+str(base/'kernel/tools/system'),flush=True)
        with Machine(base/'kernel/Image',base/'rootfs.img',display=display,debug=debug,log=base/'qemu-interactive.log') as q:
            try: q.process.wait()
            except KeyboardInterrupt: pass
    else:
        exe=base/('pc' if n==2 else LABEL[n])
        defaults={2:[],4:[str(ROOT/'labs/lab04/fixtures/classic.txt')],6:['fcfs','auto',str(ROOT/'labs/lab06/fixtures/original.txt')],7:['run','all','3',str(ROOT/'labs/lab07/fixtures/sequence1.txt')],8:[]}
        run([exe,*(shlex.split(args) if args else defaults[n])])


def student_dist():
    destination=ROOT/'dist/oslab-student.tar.gz'; destination.parent.mkdir(exist_ok=True)
    excluded={'.git','.tmp','.cache','build','dist','__pycache__','reference'}
    with tarfile.open(destination,'w:gz') as archive:
        for path in sorted(ROOT.rglob('*')):
            rel=path.relative_to(ROOT)
            if any(part in excluded for part in rel.parts) or path.suffix=='.pyc' or not path.is_file(): continue
            if rel.parts[:2]==('vendor','patches'): continue
            archive.add(path,arcname=str(Path('oslab-student')/rel),recursive=False)
    with tarfile.open(destination) as archive:
        if any('reference' in Path(n).parts or '/build/' in n for n in archive.getnames()):
            raise ValueError('student package leaked a reference/build path')
    print(destination)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['doctor','prepare','build','run','check','student-dist'])
    p.add_argument('lab',nargs='?',type=int,choices=range(1,10))
    p.add_argument('--impl',choices=['student','reference'],default='student')
    p.add_argument('--display',default='gtk',choices=['gtk','curses','none'])
    p.add_argument('--debug',action='store_true')
    p.add_argument('--args',default='')
    a=p.parse_args()
    try:
        if a.command=='doctor': doctor()
        elif a.command=='prepare': prepare()
        elif a.command=='student-dist': student_dist()
        elif a.lab is None: p.error('lab number required')
        else:
            with exclusive_lock(workdir(a.lab,a.impl)/'.workspace.lock'):
                if a.command=='build': build(a.lab,a.impl)
                elif a.command=='check': check(a.lab,a.impl)
                else: launch(a.lab,a.impl,a.display,a.debug,a.args)
    except (ValueError,OSError,subprocess.CalledProcessError,TimeoutError,RuntimeError) as exc:
        p.exit(1,'oslab: '+str(exc)+'\n')


if __name__=='__main__': main()
