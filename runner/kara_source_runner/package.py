"""Non-secret installation files included with the versioned Runner download."""
REQUIREMENTS='tiktoken==0.12.0\nJinja2==3.1.6\n'
DOCKERFILE='''ARG PYTHON_BASE_IMAGE=python:3.12-slim
FROM ${PYTHON_BASE_IMAGE}
ARG PIP_INDEX_URL=https://pypi.org/simple
RUN --mount=type=secret,id=kara_ca \\
    if [ -f /run/secrets/kara_ca ]; then export PIP_CERT=/run/secrets/kara_ca; fi; \\
    python -m pip install --no-cache-dir --index-url "$PIP_INDEX_URL" Jinja2==3.1.6
USER 65534:65534
'''
README='''# Kara Runner 2.1.2

Python 3.10+, Git; Windows uses WSL. Run from this extracted directory.

python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m kara_source_runner pair --server https://YOUR-KARA-HOST

Enter the one-time pairing code in the hidden terminal prompt, not command arguments.
Then select this device for each project in Kara > Settings > Personal Runners.
Existing paired devices can upgrade the package and reuse their private device.json.
Use your own Kara account and pairing on each device; never copy a teammate's device.json.
Remote VDI devices need a trusted HTTPS Kara address. Loopback HTTP is only for
Kara on the same device; do not use the server's 127.0.0.1 address on another VDI.

With Docker (isolated code execution; images must exist before jobs):
docker build -f Dockerfile.code -t kara/code-python:2.0 .
docker pull node:22-alpine
python -m kara_source_runner service install

The service command is for Linux with systemd --user. Read BACKGROUND.md for CA,
Docker group access, optional code images, updates, logout/boot and management.
It installs, enables and starts a user service without sudo. Stop any manually
running older Runner first. On other systems, run in the foreground instead:
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
Foreground mode needs an open terminal; the Linux service does not.
Device loss interrupts execution without automatic replay.
Graph/model/code execution happens locally; state, node outputs and final results are
sent to Kara. Models may remain on an external service. Repo scripts/Markdown are not
automatically executed. Remote services must be reachable from this device.
'''

SERVICE_README='''# Background Runner on Linux / VDI

Use your own account, never sudo, from the extracted package and activated venv.
Python 3.10+, Git, a paired private device.json and a working systemd user manager
are prerequisites. WSL must have systemd enabled. Other platforms use foreground mode.
The installer changes only the user service; it never installs Docker, changes groups,
weakens TLS, pairs a device, copies a token or downloads a code image.

1. Prepare the venv/dependencies and pair using README.md. Keep this directory and
   venv in a permanent private location. Stop any old foreground Runner with Ctrl+C.
2. For Docker code execution, prepare images using Dockerfile.code / README.md and
   ensure your own account can access Docker. For model/source-only use, Docker is
   optional; auto mode does not enable unsandboxed code without explicit opt-in.
3. Install, enable and start:

python -m kara_source_runner service install

Corporate VDI example (substitute your actual trusted CA file and existing group):
python -m kara_source_runner service install --ca-bundle /PATH/TO/trusted-ca.pem --docker-group docker

--ca-bundle configures SSL_CERT_FILE, REQUESTS_CA_BUNDLE and GIT_SSL_CAINFO. Without
it, existing values for these CA variables are validated and preserved. The CA file
must stay available. No CA/private key content goes into the unit. --docker-group
uses sg for an existing membership, keeping your UID; ask IT for access if needed.
Docker group access grants administrative control of Docker; socket permissions are
never changed. PATH and explicit Docker endpoint/context/config selection are saved;
the rest of your interactive shell environment is not copied. No shell startup files
are sourced. Configure any personal harness's absolute executable path separately.

No Docker image is automatically pulled. With a corporate mirror/CA, build Python
using a trusted base image and an HTTPS package index (no embedded credentials):
docker build -f Dockerfile.code -t kara/code-python:2.0 --build-arg PYTHON_BASE_IMAGE=python:3.12-bookworm --build-arg PIP_INDEX_URL=https://YOUR-MIRROR/simple/ --secret id=kara_ca,src=/PATH/TO/trusted-ca.pem .

The certificate is a build secret and is not copied into the image. Keep TLS enabled.
JavaScript code separately needs the node:22-alpine image. Use service restart after
preparing code images or changing local dependencies, when no job is in progress.

Management (no pairing or source deletion):
python -m kara_source_runner service status
python -m kara_source_runner service logs
python -m kara_source_runner service stop
python -m kara_source_runner service start
python -m kara_source_runner service restart
python -m kara_source_runner service uninstall

Stop/restart/uninstall interrupts active work; an interrupted job is not replayed.
Status/logs are local; service active alone does not prove connectivity. Check online
state in Kara and perform one small source/code check after setup. Do not share logs
without reviewing them for private paths/data. New Runner versions refuse a second
process for the same paired config. Older versions lack this protection: stop them first.

The unit is ~/.config/systemd/user/kara-source-runner.service (or under XDG_CONFIG_HOME).
It uses the installing venv and package, Restart=always, SIGINT, private umask and
the user journal. Existing different/manual units are never silently overwritten.
Repeated installation with identical settings starts the existing service unchanged.

Updates: stop the service before replacing package files in place. Preserve venv,
private pairing, workspace root and personal harness settings. Then start it again.
If changing service options or adopting a manual unit, review and re-specify ALL custom
options with service install --replace; the old unit is backed up privately. Replacement
restarts the service and can interrupt a job. This includes the previously manual VDI
unit; it keeps working without migration until you explicitly replace it. uninstall
removes only an installer-managed unit; backups, credentials and sources are kept.
For a custom paired config, put --config /PATH/device.json before service install.
Only one service name is managed per OS account; another config requires explicit replacement.
Run options such as --root, --code-backend, --python-image, --javascript-image,
--allow-worktree-write, --allow-harness and --harness-config also work after service install.
Unsandboxed process code still requires BOTH --code-backend process and --allow-local-code.
Enabling managed personal harnesses still requires --allow-harness and trusted private profiles.

Closing a terminal does not stop this service. Logout/boot persistence also requires
an active user manager / lingering and available home/venv, Docker, network and CA:
loginctl show-user "$(id -u)" --property=Linger
If lingering is disabled, ask your administrator about enabling it for your own account.
The installer never changes lingering or reboots/logs out. Test a real logout/reboot
at an agreed time before claiming acceptance on another VDI. Service restart never
means replay of interrupted work. To stop autostart, uninstall (data are preserved).
'''

HARNESS_PROFILES='[\n  {"key":"codex","name":"My Codex","kind":"codex","version":"","executable":"/ABSOLUTE/PATH/TO/codex","timeout":1800},\n  {"key":"opencode","name":"My OpenCode","kind":"opencode","version":"","executable":"/ABSOLUTE/PATH/TO/opencode","timeout":1800}\n]\n'
HARNESS_README='# Personal harnesses in Kara\n\nManual/interactive:\nChoose the personal harness method in the Kara task, start it, then prepare its task worktrees:\npython -m kara_source_runner harness-prepare --attempt ATTEMPT_UUID\nUse the same --root as source preparation, if customized. Read .kara-task/TASK.md in the printed worktree.\nUse any installed tool yourself, then upload/fill its result in the same Kara task.\n\nManaged execution (explicit opt-in, OS account permissions):\nCopy harnesses.example.json to ~/.config/kara-source-runner/harnesses.json WITHOUT overwriting existing settings.\nRemove unused profiles, set absolute installed executable paths, then chmod 600 that file.\npython -m kara_source_runner run --allow-harness\nOptional --harness-config chooses a different private JSON profile list.\nNo tool is installed or signed in automatically. Model/account settings belong to each harness.\nCodex runs noninteractively with workspace-write; OpenCode 2 uses a private standalone server and JSON events; older versions use manual mode. No auto-approval flags.\nFor GUI/interactive approval needs, use manual mode instead. Existing GUI sessions are not attached.\n\nA custom profile uses kind=custom, executable=/absolute/trusted/script and argv=["{bundle}","{result}","{worktree}"].\nOnly exact placeholder tokens are substituted. The script must write the result file and exit zero.\nThe server never supplies executable/argv. These settings remain local; metadata/digests go to Kara.\nDocker code-node isolation does not isolate a personal harness. Enable only trusted tools.\nCancellation/lease loss stops a managed subprocess; interrupted runs are never replayed automatically.\nPending completed deliveries are flushed before profile registration changes. CLI stdout is bounded in memory; only the final OpenCode text message is parsed.\nNo automatic push/merge. Human finalization in Kara is still required to unlock the next stage.\nA profile timeout is 30..3600 seconds, default 1800. Keep output within the task contract and 512 KiB.\nTests must be reported as not_run when not executed. Harness-reported success is not verified test evidence.\nA programme with a declared native output validator must first gain a compatible harness contract.\n'

def extras():return {'requirements.txt':REQUIREMENTS,'Dockerfile.code':DOCKERFILE,'README.md':README,'BACKGROUND.md':SERVICE_README,'HARNESS.md':HARNESS_README,'harnesses.example.json':HARNESS_PROFILES}
