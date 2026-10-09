"""Build a reproducible projects extension image; keep upstream untouched."""
import hashlib
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
CUSTOM = ROOT / 'infra/api'
IMAGE = 'company-agent/dify-api:1.17.1-projects'


def fingerprint():
    digest = hashlib.sha256((ROOT / 'infra/dify.lock.json').read_bytes())
    for path in sorted(CUSTOM.rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc':
            digest.update(path.relative_to(CUSTOM).as_posix().encode())
            digest.update(path.read_bytes())
    digest.update(Path(__file__).read_bytes())
    return digest.hexdigest()


def image_is_current():
    result = subprocess.run(['docker', 'image', 'inspect', IMAGE, '--format',
        '{{index .Config.Labels "company-agent.projects"}}'], capture_output=True, text=True)
    return result.returncode == 0 and result.stdout.strip() == fingerprint()


def build_image():
    from local_dify import verify_checkout
    verify_checkout()
    subprocess.run(['docker', 'build', '--label', f'company-agent.projects={fingerprint()}',
                    '-t', IMAGE, str(CUSTOM)], check=True)


if __name__ == '__main__':
    build_image()
