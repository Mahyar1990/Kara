"""Bounded repair of the installed provider SDK, never the upstream checkout."""
import hashlib
import os
from pathlib import Path
import sys

PROVIDER = 'openai_api_compatible-0.0.68@ba61c5eccb814be7364117c0bec3710a51e09b20f31e37243e747a00f9377969'
BASE = Path('/app/storage/cwd/langgenius') / PROVIDER / '.venv'
TARGET = BASE / 'lib/python3.12/site-packages/dify_plugin/interfaces/model/openai_compatible/llm.py'
ORIGINAL_SHA256 = 'ec1395a95745384f9d7fc05a29e4581ceb7d006b4cb0cc2a59d0de1b7ed23358'
OLD = '                finish_reason = chunk_json["choices"][0].get("finish_reason")\n'
NEW = ('                incoming_finish_reason = choice.get("finish_reason")\n'
       '                if incoming_finish_reason is not None:\n'
       '                    finish_reason = incoming_finish_reason\n')


def digest(source):
    return hashlib.sha256(source.encode()).hexdigest()


def patched(source):
    if source.count(NEW) == 1 and digest(source.replace(NEW, OLD)) == ORIGINAL_SHA256:
        return source
    if digest(source) != ORIGINAL_SHA256 or source.count(OLD) != 1:
        raise RuntimeError('Unsupported provider SDK source; review the new version before patching')
    return source.replace(OLD, NEW)


def main():
    source = TARGET.read_text()
    result = patched(source)
    if source == result:
        print('stream SDK: verified')
    elif '--apply' not in sys.argv:
        raise RuntimeError('stream SDK repair required: python scripts/model_stream.py --apply')
    else:
        # uv may hardlink its cache. Replace this installed file atomically;
        # never modify a shared cache inode or any provider source/credentials.
        temporary = TARGET.with_suffix('.kara.tmp')
        try:
            with temporary.open('x') as output:
                output.write(result)
            temporary.chmod(TARGET.stat().st_mode & 0o777)
            os.replace(temporary, TARGET)
        finally:
            temporary.unlink(missing_ok=True)
        print('stream SDK: repaired')


if __name__ == '__main__':
    main()
