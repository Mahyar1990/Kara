"""Non-secret installation files included with the versioned Runner download."""
REQUIREMENTS='tiktoken==0.12.0\nJinja2==3.1.6\n'
DOCKERFILE='''FROM python:3.12-slim
RUN pip install --no-cache-dir Jinja2==3.1.6
USER 65534:65534
'''
README='''# Kara Runner 2.1.1

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

For personal harness tasks, read HARNESS.md and harnesses.example.json before enabling execution.
Keep the terminal running. Device loss interrupts execution without automatic replay.
Graph/model/code execution happens locally; state, node outputs and final results are
sent to Kara. Models may remain on an external service. Repo scripts/Markdown are not
automatically executed. Remote services must be reachable from this device.
'''

HARNESS_PROFILES='[\n  {"key":"codex","name":"My Codex","kind":"codex","version":"","executable":"/ABSOLUTE/PATH/TO/codex","timeout":1800},\n  {"key":"opencode","name":"My OpenCode","kind":"opencode","version":"","executable":"/ABSOLUTE/PATH/TO/opencode","timeout":1800}\n]\n'
HARNESS_README='# Personal harnesses in Kara\n\nManual/interactive:\nChoose the personal harness method in the Kara task, start it, then prepare its task worktrees:\npython -m kara_source_runner harness-prepare --attempt ATTEMPT_UUID\nUse the same --root as source preparation, if customized. Read .kara-task/TASK.md in the printed worktree.\nUse any installed tool yourself, then upload/fill its result in the same Kara task.\n\nManaged execution (explicit opt-in, OS account permissions):\nCopy harnesses.example.json to ~/.config/kara-source-runner/harnesses.json WITHOUT overwriting existing settings.\nRemove unused profiles, set absolute installed executable paths, then chmod 600 that file.\npython -m kara_source_runner run --allow-harness\nOptional --harness-config chooses a different private JSON profile list.\nNo tool is installed or signed in automatically. Model/account settings belong to each harness.\nCodex runs noninteractively with workspace-write; OpenCode 2 uses a private standalone server and JSON events; older versions use manual mode. No auto-approval flags.\nFor GUI/interactive approval needs, use manual mode instead. Existing GUI sessions are not attached.\n\nA custom profile uses kind=custom, executable=/absolute/trusted/script and argv=["{bundle}","{result}","{worktree}"].\nOnly exact placeholder tokens are substituted. The script must write the result file and exit zero.\nThe server never supplies executable/argv. These settings remain local; metadata/digests go to Kara.\nDocker code-node isolation does not isolate a personal harness. Enable only trusted tools.\nCancellation/lease loss stops a managed subprocess; interrupted runs are never replayed automatically.\nPending completed deliveries are flushed before profile registration changes. CLI stdout is bounded in memory; only the final OpenCode text message is parsed.\nNo automatic push/merge. Human finalization in Kara is still required to unlock the next stage.\nA profile timeout is 30..3600 seconds, default 1800. Keep output within the task contract and 512 KiB.\nTests must be reported as not_run when not executed. Harness-reported success is not verified test evidence.\nA programme with a declared native output validator must first gain a compatible harness contract.\n'

def extras():return {'requirements.txt':REQUIREMENTS,'Dockerfile.code':DOCKERFILE,'README.md':README,'HARNESS.md':HARNESS_README,'harnesses.example.json':HARNESS_PROFILES}
