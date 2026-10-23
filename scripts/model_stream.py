"""Verify/repair the pinned installed streaming SDK without calling a model."""
import argparse
import importlib.util
from pathlib import Path
import subprocess

import local_dify

PATCH = Path(__file__).resolve().parents[1] / 'infra/plugin/model_stream_patch.py'
spec = importlib.util.spec_from_file_location('model_stream_patch', PATCH)
repair = importlib.util.module_from_spec(spec)
spec.loader.exec_module(repair)


def check(apply=False):
    interpreter = str(repair.BASE / 'bin/python')
    # Fixed path; do not scan/mutate unrelated plugins, uv caches or upstream.
    present = local_dify.compose(['exec', '-T', 'plugin_daemon', 'sh', '-c',
        'test ! -x "$1" || printf installed', 'kara-stream', interpreter], capture=True)
    if present.stdout.strip() != 'installed':
        print('stream SDK: pinned provider not installed; no changes')
        return
    result = local_dify.compose(['exec', '-T', 'plugin_daemon', interpreter, '-c', PATCH.read_text(),
        *(['--apply'] if apply else [])], capture=True)
    print(result.stdout.strip())
    if 'stream SDK: repaired' in result.stdout:
        local_dify.compose(['restart', 'plugin_daemon'], capture=True)
        print('stream SDK: plugin daemon restarted; no model invoked')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    try:
        check(parser.parse_args().apply)
    except (RuntimeError, subprocess.CalledProcessError):
        raise SystemExit('stream SDK check failed; unsupported source or repair required; no model invoked')
