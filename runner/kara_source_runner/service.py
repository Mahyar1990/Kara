"""Opt-in Linux user service installation; never install as root or copy credentials."""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import ssl
import stat
import subprocess
import sys
import tempfile

UNIT = 'kara-source-runner.service'
MARKER = '# Managed by Kara Runner service install v1\n'


class ServiceError(Exception):
    pass


def absolute(value):
    value = os.path.abspath(os.path.expanduser(str(value)))
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ServiceError('Paths must not contain control characters.')
    return value


def quote(value, *, command=False):
    value = str(value)
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ServiceError('Service settings must not contain control characters.')
    value = value.replace('%', '%%')
    if command:
        value = value.replace('$', '$$')
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'


def private_config(path):
    path = Path(absolute(path))
    if not path.exists() and not path.is_symlink():
        raise ServiceError('Pair this device first; no existing credentials were changed.')
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ServiceError('Device config must be your private regular file (chmod 600).')
    from .client import server_url
    try:
        value = json.loads(path.read_text())
        if not isinstance(value, dict) or not isinstance(value.get('server'), str):
            raise ValueError()
        server_url(value['server'])
        if not isinstance(value['secret'], str) or not value['secret']:
            raise ValueError()
    except (ValueError, KeyError, TypeError):
        raise ServiceError('Pair this device first; existing credentials were not changed.') from None
    return path


@contextmanager
def instance_lock(config):
    """One process per paired config, regardless of workspace root or launch method."""
    import fcntl
    config = Path(absolute(config))
    digest = hashlib.sha256(str(config.resolve()).encode()).hexdigest()[:24]
    path = config.parent / ('.runner-' + digest + '.lock')
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ServiceError('Runner lock must be your private regular file.')
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ServiceError('A Runner already uses this device config; stop it before starting another.') from None
        yield
    finally:
        os.close(fd)


def checked(command, *, visible=False, env=None):
    try:
        result = subprocess.run(command, stdin=subprocess.DEVNULL,
                                stdout=None if visible else subprocess.DEVNULL,
                                stderr=None if visible else subprocess.DEVNULL,
                                timeout=40, env=env)
    except (OSError, subprocess.TimeoutExpired):
        raise ServiceError('Local service command unavailable or timed out; no credentials were printed.') from None
    if result.returncode:
        raise ServiceError('Local service command failed; check systemctl --user status and the user journal.')


def unit_path():
    base = os.environ.get('XDG_CONFIG_HOME') or str(Path.home() / '.config')
    if not Path(base).is_absolute():
        raise ServiceError('XDG_CONFIG_HOME must be an absolute path.')
    return Path(base) / 'systemd/user' / UNIT


def runner_command(args):
    command = [absolute(sys.executable), '-m', 'kara_source_runner', '--config', absolute(args.config),
               'run', '--root', absolute(args.root), '--code-backend', args.code_backend,
               '--python-image', args.python_image, '--javascript-image', args.javascript_image]
    for name in ('allow_worktree_write', 'allow_local_code', 'allow_harness'):
        if getattr(args, name):
            command.append('--' + name.replace('_', '-'))
    command += ['--harness-config', absolute(args.harness_config)]
    return command


def group_command(command, group):
    if not group:
        return command
    import grp
    import pwd
    if not group or not all(c.isalnum() or c in '_-' for c in group):
        raise ServiceError('Invalid Docker group name.')
    try:
        entry = grp.getgrnam(group)
    except KeyError:
        raise ServiceError('Docker group does not exist; ask your administrator.') from None
    user = pwd.getpwuid(os.getuid()).pw_name
    if entry.gr_gid not in os.getgroups() + [os.getgid()] and user not in entry.gr_mem:
        raise ServiceError('Your account must already belong to the requested Docker group; ask your administrator.')
    sg = shutil.which('sg')
    if not sg:
        raise ServiceError('sg is required to activate this Docker group.')
    return [sg, group, '-c', 'exec ' + shlex.join(command)]


def render_unit(args, environment):
    command = group_command(runner_command(args), args.docker_group)
    directory = absolute(Path(__file__).parent.parent)
    # WorkingDirectory takes a path, not an argv item: quotes would become part of it.
    if directory[-1].isspace() or directory.endswith('\\'):
        raise ServiceError('Keep the Runner package in a directory without trailing whitespace or backslash.')
    lines = [MARKER.rstrip(), '[Unit]', 'Description=Kara Source Runner', 'StartLimitIntervalSec=0',
             '', '[Service]', 'Type=exec', 'WorkingDirectory=' + directory.replace('%', '%%')]
    for key, value in sorted(environment.items()):
        lines.append('Environment=' + quote(key + '=' + value))
    lines += ['ExecStart=' + ' '.join(quote(v, command=True) for v in command),
              'Restart=always', 'RestartSec=10', 'KillSignal=SIGINT', 'TimeoutStopSec=30',
              'UMask=0077', 'StandardOutput=journal', 'StandardError=journal',
              '', '[Install]', 'WantedBy=default.target', '']
    return '\n'.join(lines)


def service_environment(args):
    # Do not persist shell secrets, proxy credentials, tokens or arbitrary environment.
    environment = {'PATH': os.environ.get('PATH', os.defpath), 'PYTHONUNBUFFERED': '1'}
    # Preserve explicit Docker selection; never copy the rest of the shell environment.
    for key in ('DOCKER_HOST', 'DOCKER_CONTEXT', 'DOCKER_CONFIG', 'DOCKER_TLS_VERIFY', 'DOCKER_CERT_PATH', 'XDG_RUNTIME_DIR'):
        if os.environ.get(key):
            value = os.environ[key]
            if key == 'DOCKER_HOST' and ('@' in value or '?' in value or '#' in value):
                raise ServiceError('Docker endpoint must not contain embedded credentials, query or fragment.')
            environment[key] = value
    for key in ('SSL_CERT_FILE', 'REQUESTS_CA_BUNDLE', 'GIT_SSL_CAINFO'):
        value = args.ca_bundle or os.environ.get(key)
        if value:
            path = absolute(value)
            try:
                ssl.create_default_context(cafile=path)
            except (OSError, ssl.SSLError):
                raise ServiceError('CA bundle must be a readable valid certificate file; TLS stays enabled.') from None
            environment[key] = path
    return environment


def existing_unit(path):
    if not path.exists() and not path.is_symlink():
        return None
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
        raise ServiceError('Refusing to change a symlink or a service file owned by another user.')
    return path.read_text()


def write_unit(path, content, old):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Exclusive creation for fresh installs; atomic replacement with a private backup for upgrades.
    if old is None:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'w') as handle:
            handle.write(content)
        return
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup = path.with_name(path.name + '.' + stamp + '.bak')
    fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as handle:
        handle.write(old)
    fd, temporary = tempfile.mkstemp(prefix='.kara-unit-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as handle:
            handle.write(content)
        if existing_unit(path) != old:
            raise ServiceError('Service file changed during installation; retry after reviewing it.')
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    print('Previous service saved:', backup)


def install(args, systemctl):
    private_config(args.config)
    if args.code_backend == 'process' and not args.allow_local_code:
        raise ServiceError('Process code execution needs explicit --allow-local-code; use auto to leave code disabled without Docker.')
    environment = service_environment(args)
    content = render_unit(args, environment)
    path = unit_path()
    old = existing_unit(path)
    if old is not None and old != content and not args.replace:
        raise ServiceError('Service already exists with other settings. Keep it, or review all options and use service install --replace; a backup will be kept.')
    # Manager access is checked before any filesystem mutation.
    checked([systemctl, '--user', 'show-environment'])
    analyzer = shutil.which('systemd-analyze')
    if analyzer:
        with tempfile.TemporaryDirectory(prefix='kara-service-check-') as temporary:
            candidate = Path(temporary) / UNIT
            candidate.write_text(content)
            candidate.chmod(0o600)
            checked([analyzer, '--user', 'verify', str(candidate)])
    if not shutil.which('git'):
        raise ServiceError('Git is required on this device.')
    if args.code_backend == 'docker' or (args.code_backend == 'auto' and shutil.which('docker')):
        docker = shutil.which('docker')
        if not docker:
            raise ServiceError('Docker is required for the selected backend.')
        probe = group_command([docker, 'info', '--format', '{{.ServerVersion}}'], args.docker_group)
        try:
            checked(probe, env={**{k: v for k, v in os.environ.items() if k in ('HOME', 'LANG', 'LC_ALL')}, **environment})
        except ServiceError:
            raise ServiceError('Docker is unavailable to this account. Start Docker or ask IT for access; --docker-group activates existing membership only.') from None
        print('Docker access checked. Prepare code images separately; installation never pulls images.')
    # An older Runner does not have this lock: stop any manually launched old version first.
    active = subprocess.run([systemctl, '--user', 'is-active', '--quiet', UNIT],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10).returncode == 0
    if active and old is None:
        raise ServiceError('A service with this name is already loaded elsewhere; inspect it before installation.')
    if active and old != content:
        checked([systemctl, '--user', 'stop', UNIT])
    if not active or old != content:
        try:
            with instance_lock(args.config):
                pass
        except ServiceError:
            if active:
                checked([systemctl, '--user', 'start', UNIT])
            raise
    if old != content:
        try:
            write_unit(path, content, old)
        except (OSError, ServiceError):
            if active:
                checked([systemctl, '--user', 'start', UNIT])
            raise
    checked([systemctl, '--user', 'daemon-reload'])
    checked([systemctl, '--user', 'enable', UNIT])
    checked([systemctl, '--user', 'restart' if old is not None and old != content else 'start', UNIT])
    checked([systemctl, '--user', 'is-active', '--quiet', UNIT])
    print('Runner service enabled and active. Check service status/logs and online state in Kara.')
    print('No pairing or source files changed. Keep the extracted package and its virtual environment in place.')
    print('For operation after logout/boot, check loginctl show-user YOUR_USER --property=Linger; ask your administrator if needed.')


def manage(args):
    if not sys.platform.startswith('linux'):
        raise ServiceError('Background service installation supports Linux with systemd --user; on Windows use a systemd-enabled WSL distribution.')
    if os.getuid() == 0:
        raise ServiceError('Run service commands as your own account without sudo.')
    systemctl = shutil.which('systemctl')
    if not systemctl:
        raise ServiceError('systemctl is unavailable; use a Linux system with a user service manager.')
    action = args.service_action
    if action == 'install':
        install(args, systemctl)
        return 0
    path = unit_path()
    content = existing_unit(path)
    if content is None or not content.startswith(MARKER):
        raise ServiceError('No service managed by this installer. Existing manual services are preserved; inspect them with systemctl --user status kara-source-runner.service.')
    if action == 'uninstall':
        checked([systemctl, '--user', 'disable', '--now', UNIT])
        if existing_unit(path) != content:
            raise ServiceError('Service file changed during uninstall; it was preserved for review.')
        path.unlink()
        checked([systemctl, '--user', 'daemon-reload'])
        print('Service removed. Pairing, source files, package and backups were preserved.')
        return 0
    if action == 'logs':
        journalctl = shutil.which('journalctl')
        if not journalctl:
            raise ServiceError('journalctl is unavailable.')
        command = [journalctl, '--user', '-u', UNIT, '-n', '40', '--no-pager']
    else:
        command = [systemctl, '--user', action, UNIT]
        if action == 'status':
            command += ['--no-pager', '-l']
    return subprocess.run(command, timeout=40).returncode


def add_run_options(parser):
    parser.add_argument('--root', type=Path, default=Path.home() / 'KaraSourceWorkspaces')
    parser.add_argument('--python-image', default='kara/code-python:2.0')
    parser.add_argument('--javascript-image', default='node:22-alpine')
    parser.add_argument('--allow-worktree-write', action='store_true')
    parser.add_argument('--code-backend', choices=['auto', 'docker', 'process'], default='auto')
    parser.add_argument('--allow-local-code', action='store_true')
    parser.add_argument('--allow-harness', action='store_true')
    parser.add_argument('--harness-config', type=Path, default=Path.home() / '.config/kara-source-runner/harnesses.json')


def add_parser(sub):
    parser = sub.add_parser('service', help='Manage your Linux background Runner without sudo.')
    actions = parser.add_subparsers(dest='service_action', required=True)
    install_parser = actions.add_parser('install', help='Install, enable and start your user service.')
    add_run_options(install_parser)
    install_parser.add_argument('--ca-bundle', type=Path, help='Corporate CA certificate bundle for HTTPS and Git.')
    install_parser.add_argument('--docker-group', help='Activate an existing group membership using sg; never changes groups.')
    install_parser.add_argument('--replace', action='store_true', help='Replace changed or manual unit, keeping a private backup; re-specify all custom settings.')
    for action in ('start', 'stop', 'restart', 'status', 'logs', 'uninstall'):
        actions.add_parser(action)
