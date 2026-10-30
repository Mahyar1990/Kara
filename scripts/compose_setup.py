"""Prepare Docker build contexts using only the bootstrap container's tools."""
import json
import os
from pathlib import Path
import subprocess
import sys

import company_api
import local_dify
import persian_web

ROOT = Path(__file__).resolve().parents[1]


def use_workspace_owner():
    # On Linux, avoid leaving root-owned generated files in the developer's clone.
    # Docker Desktop handles bind-mount ownership in its VM.
    if hasattr(os, 'geteuid') and os.geteuid() == 0:
        owner = ROOT.stat()
        os.setgroups([])
        os.setgid(owner.st_gid)
        os.setuid(owner.st_uid)
    # Trust only this mounted clone, without changing a user's Git configuration.
    os.environ['GIT_CONFIG_COUNT'] = '1'
    os.environ['GIT_CONFIG_KEY_0'] = 'safe.directory'
    os.environ['GIT_CONFIG_VALUE_0'] = str(ROOT)


def prepare():
    # Check the private catalog dependency before downloads or configuration writes.
    company_api.catalog_files()
    local_dify.prepare()
    company_api.prepare_source()
    persian_web.prepare_source()
    values = local_dify.settings()
    environment = (local_dify.DOCKER_DIR / '.env').read_text(encoding='utf-8')
    # Preserve existing credentials; only the launcher's public overrides differ.
    public = local_dify.public_environment(values)
    # Replace all occurrences; never append a second conflicting value.
    lines = [line for line in environment.splitlines() if line.partition('=')[0] not in public]
    environment = '\n'.join(lines + [f"{key}={value}" for key, value in public.items()]) + '\n'
    target = ROOT / '.runtime/compose.env'
    with target.open('w', encoding='utf-8') as output:
        target.chmod(0o600)
        output.write(environment)
    # JSON is valid YAML. Labels keep make doctor compatible with Compose builds.
    (ROOT / '.runtime/compose.build.json').write_text(json.dumps({'services': {
        'api': {'build': {'labels': {'company-agent.projects': company_api.fingerprint()}}},
        'web': {'build': {'labels': {'company-agent.localization': persian_web.fingerprint()}}},
    }}, indent=2) + '\n', encoding='utf-8')
    print('Kara sources and private configuration are ready. Run: docker compose up -d --build')
    if values['DIFY_PROJECT_NAME'] != 'company-agent-local':
        print(f"Use docker compose -p {values['DIFY_PROJECT_NAME']} for your custom project name.")


if __name__ == '__main__':
    try:
        use_workspace_owner()
        prepare()
    except (RuntimeError, ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f'Setup failed: {error}', file=sys.stderr)
        sys.exit(1)
