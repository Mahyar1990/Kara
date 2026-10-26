"""Non-secret installation files included with the versioned Runner download."""
REQUIREMENTS='tiktoken==0.12.0\nJinja2==3.1.6\n'
DOCKERFILE='''FROM python:3.12-slim
RUN pip install --no-cache-dir Jinja2==3.1.6
USER 65534:65534
'''
README='''# Kara Runner 2

Python 3.10+, Git; Windows uses WSL. Run from this extracted directory.

python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m kara_source_runner pair --server https://YOUR-KARA-HOST

Enter the one-time pairing code in the hidden terminal prompt, not command arguments.
Then select this device for each project in Kara > Settings > Personal Runners.
Existing paired devices can upgrade the package and reuse their private device.json.

With Docker (isolated code execution; images must exist before jobs):
docker build -f Dockerfile.code -t kara/code-python:2.0 .
docker pull node:22-alpine
python -m kara_source_runner run

Without Docker (trusted programs only; NO OS SANDBOX):
python -m kara_source_runner run --code-backend process --allow-local-code

This explicitly permits published code to run with your OS account's file/network
permissions. A separate process and resource/time limits do not provide a sandbox.
Without this flag, a device lacking Docker will not claim code-requiring jobs.

--root changes the source workspace root. --config before the action chooses a
separate paired account. --allow-worktree-write mounts the selected source snapshot
writable in Docker. Process mode has no filesystem isolation; this flag only chooses
that worktree as its working directory. Credentials are not passed into code nodes.

Keep the terminal running. Device loss interrupts execution without automatic replay.
Graph/model/code execution happens locally; state, node outputs and final results are
sent to Kara. Models may remain on an external service. Repo scripts/Markdown are not
automatically executed. Remote services must be reachable from this device.
'''

def extras():return {'requirements.txt':REQUIREMENTS,'Dockerfile.code':DOCKERFILE,'README.md':README}
