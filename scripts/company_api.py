"""Build a reproducible projects extension image; keep upstream untouched."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
CUSTOM = ROOT / 'infra/api'
IMAGE = 'company-agent/dify-api:1.17.1-projects'


def catalog_files():
    # Only committed, pinned assets from the agents history enter the image.
    lock = json.loads((ROOT / 'infra/catalog.lock.json').read_text())
    if not re.fullmatch(r'[a-f0-9]{40}', lock['commit']) or lock['directory'] != 'workflows/starter-library':
        raise RuntimeError('Invalid catalog lock')
    def blob(filename):
        if not re.fullmatch(r'[a-z][a-z0-9-]*\.json', filename):
            raise RuntimeError('Invalid catalog file name')
        result = subprocess.run(['git', 'show', f"{lock['commit']}:{lock['directory']}/{filename}"],
            cwd=ROOT, capture_output=True)
        if result.returncode:
            raise RuntimeError(
                f"Pinned template catalog is missing from Git history. Run git fetch origin {lock['commit']} "
                "on the host, then retry setup. Use a full clone rather than a source ZIP."
            )
        return result.stdout
    files = {'catalog.json': blob('catalog.json')}
    catalog = json.loads(files['catalog.json'])
    if catalog['schema_version'] != 1 or len(catalog['templates']) > 50:
        raise RuntimeError('Unsupported catalog')
    for template in catalog['templates']:
        files[template['file']] = blob(template['file'])
    return files


def fingerprint():
    digest = hashlib.sha256((ROOT / 'infra/dify.lock.json').read_bytes())
    for path in sorted(CUSTOM.rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc':
            digest.update(path.relative_to(CUSTOM).as_posix().encode())
            digest.update(path.read_bytes())
    for path in sorted((ROOT / 'runner/kara_source_runner').rglob('*.py')):
        digest.update(path.relative_to(ROOT).as_posix().encode()); digest.update(path.read_bytes())
    digest.update(Path(__file__).read_bytes())
    digest.update((ROOT / 'infra/catalog.lock.json').read_bytes())
    for name, content in sorted(catalog_files().items()):
        digest.update(name.encode()); digest.update(content)
    return digest.hexdigest()


def image_is_current():
    result = subprocess.run(['docker', 'image', 'inspect', IMAGE, '--format',
        '{{index .Config.Labels "company-agent.projects"}}'], capture_output=True, text=True)
    return result.returncode == 0 and result.stdout.strip() == fingerprint()


def prepare_source():
    from local_dify import verify_checkout
    verify_checkout()
    context = ROOT / '.runtime/company-api-source'
    if context.exists():
        shutil.rmtree(context)
    shutil.copytree(CUSTOM, context, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    shutil.copytree(ROOT / 'runner/kara_source_runner', context / 'kara_source_runner', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    templates = context / 'company_templates'
    templates.mkdir()
    for name, content in catalog_files().items():
        (templates / name).write_bytes(content)
    shutil.copyfile(ROOT / 'infra/catalog.lock.json', templates / 'source.json')
    return context


def build_image():
    context = prepare_source()
    subprocess.run(['docker', 'build', '--label', f'company-agent.projects={fingerprint()}',
                    '-t', IMAGE, str(context)], check=True)


if __name__ == '__main__':
    build_image()
