#!/usr/bin/env python3
"""Prepare and operate the pinned, private local Dify deployment."""

import argparse
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM = ROOT / ".runtime" / "dify"
DOCKER_DIR = UPSTREAM / "docker"
LOCK = ROOT / "infra" / "dify.lock.json"
OVERRIDE = ROOT / "infra" / "compose.local.yaml"


def run(args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def settings():
    values = {
        "DIFY_HTTP_PORT": "8080",
        "DIFY_HTTPS_PORT": "8443",
        "DIFY_PROJECT_NAME": "company-agent-local",
    }
    config = ROOT / ".env.local"
    if config.exists():
        for line in config.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, separator, value = line.partition("=")
            if not separator or key.strip() not in values:
                raise ValueError("Unknown or invalid local setting")
            values[key.strip()] = value.strip()
    for key in ("DIFY_HTTP_PORT", "DIFY_HTTPS_PORT"):
        port = int(values[key])
        if not 1024 <= port <= 65535:
            raise ValueError("Local ports must be between 1024 and 65535")
    if values["DIFY_HTTP_PORT"] == values["DIFY_HTTPS_PORT"]:
        raise ValueError("HTTP and HTTPS ports must differ")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", values["DIFY_PROJECT_NAME"]):
        raise ValueError("Invalid Compose project name")
    return values


def verify_checkout():
    expected = json.loads(LOCK.read_text())
    if not (UPSTREAM / ".git").exists():
        raise RuntimeError("Run make setup first")
    actual = run(
        ["git", "-C", str(UPSTREAM), "rev-parse", "HEAD"],
        capture_output=True, text=True,
    ).stdout.strip()
    if actual != expected["commit"]:
        raise RuntimeError("Dify checkout differs from infra/dify.lock.json")
    return expected


def prepare():
    expected = json.loads(LOCK.read_text())
    if not UPSTREAM.exists():
        UPSTREAM.parent.mkdir(parents=True, exist_ok=True)
        run(["git", "clone", "--depth", "1", "--branch", expected["ref"],
             expected["repository"], str(UPSTREAM)])
    verify_checkout()
    target = DOCKER_DIR / ".env"
    if target.exists():
        print("Existing private Dify configuration preserved.")
        return
    values = settings()
    overrides = {
        "EXPOSE_NGINX_PORT": values["DIFY_HTTP_PORT"],
        "EXPOSE_NGINX_SSL_PORT": values["DIFY_HTTPS_PORT"],
        "CELERY_WORKER_AMOUNT": "1",
        "SERVER_WORKER_AMOUNT": "1",
        "COMPOSE_PROFILES": "postgresql,weaviate,websocket",
        "NEXT_PUBLIC_SOCKET_URL": f"ws://localhost:{values['DIFY_HTTP_PORT']}",
        "SECRET_KEY": secrets.token_hex(32),
        "DB_PASSWORD": secrets.token_hex(24),
        "REDIS_PASSWORD": secrets.token_hex(24),
        "SANDBOX_API_KEY": secrets.token_hex(32),
        "PLUGIN_DAEMON_KEY": secrets.token_hex(32),
        "PLUGIN_DIFY_INNER_API_KEY": secrets.token_hex(32),
        "DIFY_AGENT_API_TOKEN": secrets.token_hex(32),
        "DIFY_AGENT_SERVER_SECRET_KEY": secrets.token_urlsafe(32),
        "DIFY_AGENT_LOCAL_SANDBOX_AUTH_TOKEN": secrets.token_hex(32),
    }
    overrides["CELERY_BROKER_URL"] = (
        f"redis://:{overrides['REDIS_PASSWORD']}@redis:6379/1"
    )
    template = (DOCKER_DIR / ".env.example").read_text()
    lines = []
    replaced = set()
    for line in template.splitlines():
        key = line.partition("=")[0]
        if key in overrides:
            line = f"{key}={overrides[key]}"
            replaced.add(key)
        lines.append(line)
    for key, value in overrides.items():
        if key not in replaced:
            lines.append(f"{key}={value}")
    with target.open("x") as handle:
        os.chmod(target, 0o600)
        handle.write("\n".join(lines) + "\n")
    print(f"Dify {expected['version']} prepared; private settings are outside Git.")


def compose_command():
    if shutil.which("docker"):
        probe = subprocess.run(
            ["docker", "compose", "version"], capture_output=True,
        )
        if probe.returncode == 0:
            return ["docker", "compose"]
    if shutil.which("docker-compose"):
        return ["docker-compose"]
    raise RuntimeError("Install Docker and Docker Compose first")


def compose(args, capture=False):
    verify_checkout()
    if not (DOCKER_DIR / ".env").exists():
        raise RuntimeError("Private settings missing; run make setup")
    values = settings()
    environment = os.environ.copy()
    # Keep local port overrides consistent even when an existing .env is preserved.
    environment["EXPOSE_NGINX_PORT"] = values["DIFY_HTTP_PORT"]
    environment["EXPOSE_NGINX_SSL_PORT"] = values["DIFY_HTTPS_PORT"]
    environment["NEXT_PUBLIC_SOCKET_URL"] = f"ws://localhost:{values['DIFY_HTTP_PORT']}"
    command = compose_command() + [
        "--parallel", "2",
        "--project-name", values["DIFY_PROJECT_NAME"],
        "--project-directory", str(DOCKER_DIR),
        "--env-file", str(DOCKER_DIR / ".env"),
        "-f", str(DOCKER_DIR / "docker-compose.yaml"),
        "-f", str(OVERRIDE),
    ] + args
    return run(command, cwd=DOCKER_DIR, env=environment,
               capture_output=capture, text=True)


def doctor():
    verify_checkout()
    if not shutil.which("docker"):
        raise RuntimeError("Docker client is missing")
    run(["docker", "info", "--format", "Docker server: {{.ServerVersion}}"])
    # Capture the resolved config to validate bindings without printing credentials.
    resolved = json.loads(compose(["config", "--format", "json"], capture=True).stdout)
    for name, service in resolved["services"].items():
        for port in service.get("ports", []):
            if port.get("host_ip") != "127.0.0.1":
                raise RuntimeError(f"Unexpected non-local port binding: {name}")
    compose(["ps"])
    url = f"http://127.0.0.1:{settings()['DIFY_HTTP_PORT']}/install"
    try:
        with urllib.request.urlopen(url, timeout=15) as response:
            print(f"Dify web check: HTTP {response.status}; {url}")
        with urllib.request.urlopen(
            f"http://127.0.0.1:{settings()['DIFY_HTTP_PORT']}/console/api/ping",
            timeout=15,
        ) as response:
            payload = json.load(response)
            if payload.get("result") != "pong":
                raise RuntimeError("Dify API returned an unexpected health response")
            print("Dify API check: pong")
    except (urllib.error.URLError, TimeoutError) as error:
        raise RuntimeError("Dify is not ready yet; inspect make status and make logs") from error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["setup", "up", "down", "status", "logs", "doctor"])
    action = parser.parse_args().action
    if action == "setup":
        prepare()
    elif action == "up":
        prepare()
        compose(["config", "--quiet"])
        compose(["up", "-d", "--quiet-pull"])
        print(f"Dify: http://localhost:{settings()['DIFY_HTTP_PORT']}")
    elif action == "down":
        compose(["down"])
        print("Services stopped; local data preserved.")
    elif action == "status":
        compose(["ps"])
    elif action == "logs":
        compose(["logs", "--tail", "80", "api", "web", "worker"])
    else:
        doctor()


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, subprocess.CalledProcessError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
