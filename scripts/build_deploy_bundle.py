"""Create a source-only deployment snapshot; never reads .env or user databases.

stage: creates a fresh .runtime/cloud-deploy/icare-release directory.
package: archives the prepared staging directory (after dependency updates/checks).
"""
from __future__ import annotations
import hashlib
import json
import shutil
import sqlite3
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '.runtime/cloud-deploy'
STAGE = OUT / 'icare-release'
TREES = {
    'backend/app': {'.py', '.json'},
    'backend/tests': {'.py'},
    'frontend/app': {'.tsx', '.css', '.ts'},
    'frontend/components': {'.tsx', '.ts'},
    'frontend/lib': {'.ts'},
    'frontend/tests': {'.mjs'},
    'frontend/public': {'.png', '.jpg', '.jpeg', '.svg', '.ico', '.pdf', '.webmanifest'},
    'deploy/google-cloud': {'.sh', '.in', '.md', '.example'},
}
FILES = ['backend/requirements.txt', 'frontend/package.json', 'frontend/package-lock.json',
         'frontend/tsconfig.json', 'frontend/next-env.d.ts', 'frontend/next.config.mjs',
         'deploy/google-cloud/Caddyfile']
SKIP = {'node_modules', '.next', '__pycache__', '.venv'}

def allowed(path: Path) -> bool:
    if any(part in SKIP or part.startswith('.') for part in path.parts):
        return False
    name = path.as_posix()
    if name in FILES or name == 'SHA256SUMS': return True
    if name in ('backend/data/kb.openai.sqlite3', 'backend/data/kb.gemini.sqlite3'): return True
    return any(name.startswith(tree + '/') and path.suffix in extensions
               for tree, extensions in TREES.items())

def stage():
    if STAGE.exists(): raise SystemExit('Staging directory already exists; keep it or choose a new release directory.')
    STAGE.mkdir(parents=True, mode=0o700)
    selected = {ROOT / p for p in FILES}
    for tree in TREES:
        selected.update(p for p in (ROOT / tree).rglob('*') if p.is_file() and allowed(p.relative_to(ROOT)))
    for src in sorted(selected):
        if src.is_symlink(): raise SystemExit(f'Refusing symbolic link: {src.relative_to(ROOT)}')
        dest = STAGE / src.relative_to(ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
    manifest = STAGE / 'frontend/package.json'
    package_json = json.loads(manifest.read_text())
    package_json['dependencies'].update({'next': '15.5.27', 'react': '19.0.8', 'react-dom': '19.0.8'})
    package_json.setdefault('overrides', {}).update({'postcss': '8.5.29', 'nanoid': '3.3.20'})
    manifest.write_text(json.dumps(package_json, indent=2) + '\n')
    for name in ('kb.openai.sqlite3', 'kb.gemini.sqlite3'):
        source = ROOT / 'backend/data' / name
        dest = STAGE / 'backend/data' / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(source.resolve().as_uri() + '?mode=ro', uri=True) as src:
            tables = {r[0] for r in src.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if tables != {'chunks', 'meta'}: raise SystemExit('Unexpected KB tables; aborting export.')
            with sqlite3.connect(dest) as target:
                src.backup(target)
                if target.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise SystemExit('KB snapshot integrity check failed.')
    print(STAGE)
    print('Run npm install in the staged frontend to update its lockfile, then validate before packaging.')

def package():
    if not STAGE.is_dir(): raise SystemExit('Run stage first.')
    # Never package development caches or any newly created .env/database file.
    files = sorted(p for p in STAGE.rglob('*') if p.is_file()
                   and allowed(p.relative_to(STAGE)) and p.name != 'SHA256SUMS')
    for p in files:
        if p.is_symlink(): raise SystemExit('Refusing symbolic link in release.')
    versions = json.loads((STAGE / 'frontend/package.json').read_text())['dependencies']
    if versions['next'] != '15.5.27' or versions['react'] != '19.0.8' or versions['react-dom'] != '19.0.8':
        raise SystemExit('Apply the verified deployment dependency pins before packaging.')
    manifest = STAGE / 'SHA256SUMS'
    manifest.write_text(''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(STAGE).as_posix()}\n' for p in files))
    archive = OUT / 'icare-deploy.tar.gz'
    with tarfile.open(archive, 'w:gz') as tar:
        for p in files + [manifest]:
            info = tar.gettarinfo(str(p), arcname='icare-release/' + p.relative_to(STAGE).as_posix())
            info.uid = info.gid = 0
            info.uname = info.gname = ''
            info.mode = 0o644
            with p.open('rb') as file: tar.addfile(info, file)
    archive.chmod(0o600)
    with tarfile.open(archive) as tar:
        for entry in tar.getmembers():
            rel = Path(entry.name).relative_to('icare-release')
            if not entry.isfile() or '..' in rel.parts or not allowed(rel):
                raise SystemExit('Unexpected archive entry.')
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (OUT / 'icare-deploy.tar.gz.sha256').write_text(f'{digest}  icare-deploy.tar.gz\n')
    print(json.dumps({'archive':str(archive), 'files':len(files)+1,
                      'bytes':archive.stat().st_size, 'sha256':digest}))

if __name__ == '__main__':
    action = sys.argv[1] if len(sys.argv) == 2 else ''
    if action == 'stage': stage()
    elif action == 'package': package()
    else: raise SystemExit('Usage: python3 scripts/build_deploy_bundle.py stage|package')
