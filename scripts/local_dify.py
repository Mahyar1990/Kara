#!/usr/bin/env python3
"""Prepare and operate the pinned, private local Dify deployment."""

import argparse
import ipaddress
from urllib.parse import urlsplit
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import time
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
        "DIFY_BIND_ADDRESS": "127.0.0.1",
        "DIFY_PUBLIC_URL": "",
        "KARA_NPM_REGISTRY": "https://registry.npmjs.org/",
        "KARA_CA_BUNDLE": "",
        "KARA_BOOTSTRAP_IMAGE": "python:3.12-bookworm",
        "KARA_TOOLS_IMAGE": "python:3.12-bookworm",
        "DIFY_WEAVIATE_IMAGE": "cr.weaviate.io/semitechnologies/weaviate:1.39.2",
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
    address = ipaddress.ip_address(values["DIFY_BIND_ADDRESS"])
    if address.version != 4:
        raise ValueError("DIFY_BIND_ADDRESS must be an IPv4 address")
    for key, schemes in (("DIFY_PUBLIC_URL", ("http", "https")),
                         ("KARA_NPM_REGISTRY", ("https",))):
        if not values[key] and key == "DIFY_PUBLIC_URL":
            continue
        url = urlsplit(values[key])
        if (url.scheme not in schemes or not url.hostname or url.username or url.password
                or url.query or url.fragment or any(c.isspace() for c in values[key])):
            raise ValueError(f"Invalid {key}; credentials are not supported in URLs")
        if key == "DIFY_PUBLIC_URL" and url.path not in ("", "/"):
            raise ValueError("DIFY_PUBLIC_URL must be an origin without a path")
        url.port  # Validate port syntax/range.
        values[key] = url.geturl()
    if not address.is_loopback and not values["DIFY_PUBLIC_URL"]:
        raise ValueError("Network binding requires DIFY_PUBLIC_URL")
    for key in ("KARA_BOOTSTRAP_IMAGE", "KARA_TOOLS_IMAGE", "DIFY_WEAVIATE_IMAGE"):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/:@-]*", values[key]):
            raise ValueError(f"Invalid {key}")
    return values


def public_environment(values):
    origin = values.get("DIFY_PUBLIC_URL", "").rstrip("/")
    socket = origin.replace("https://", "wss://", 1).replace("http://", "ws://", 1) if origin else "ws://localhost"
    return {
        "EXPOSE_NGINX_PORT": values["DIFY_HTTP_PORT"],
        "EXPOSE_NGINX_SSL_PORT": values["DIFY_HTTPS_PORT"],
        "KARA_BIND_ADDRESS": values.get("DIFY_BIND_ADDRESS", "127.0.0.1"),
        "NEXT_PUBLIC_SOCKET_URL": socket,
        "CONSOLE_WEB_URL": origin,
        "CONSOLE_API_URL": origin,
        "APP_WEB_URL": origin,
        "SERVICE_API_URL": origin,
        "APP_API_URL": origin,
        "KARA_NPM_REGISTRY": values.get("KARA_NPM_REGISTRY", "https://registry.npmjs.org/"),
        "KARA_TOOLS_IMAGE": values.get("KARA_TOOLS_IMAGE", "python:3.12-bookworm"),
        "DIFY_WEAVIATE_IMAGE": values.get("DIFY_WEAVIATE_IMAGE", "cr.weaviate.io/semitechnologies/weaviate:1.39.2"),
    }


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
    from build_environment import configure_ca
    configure_ca()
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
        "COMPOSE_PROFILES": "postgresql,weaviate,collaboration",
        **public_environment(values),
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
    environment.update(public_environment(values))
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


def local_open(url, timeout):
    return urllib.request.build_opener(urllib.request.ProxyHandler({})).open(url, timeout=timeout)


def wait_for_api(timeout=300):
    """Allow the first app import and migrations to finish before reporting ready."""
    values = settings()
    host = values.get('DIFY_BIND_ADDRESS', '127.0.0.1')
    host = '127.0.0.1' if host == '0.0.0.0' else host
    url = f"http://{host}:{values['DIFY_HTTP_PORT']}/console/api/ping"
    deadline = time.monotonic() + timeout
    print("Waiting for Dify API readiness...", flush=True)
    while time.monotonic() < deadline:
        try:
            with local_open(url, timeout=5) as response:
                if json.load(response).get("result") == "pong":
                    print("Dify API is ready.", flush=True)
                    return
        except (urllib.error.URLError, TimeoutError, ConnectionResetError, json.JSONDecodeError):
            pass
        time.sleep(2)
    raise RuntimeError("Dify did not become ready within 5 minutes; inspect make logs")


def doctor(server_only=False):
    verify_checkout()
    if not shutil.which("docker"):
        raise RuntimeError("Docker client is missing")
    run(["docker", "info", "--format", "Docker server: {{.ServerVersion}}"])
    from persian_web import fingerprint
    web_container = compose(["ps", "-q", "web"], capture=True).stdout.strip()
    if not web_container:
        raise RuntimeError("Web service is not running; run make up")
    web_revision = run(
        ["docker", "inspect", web_container, "--format",
         '{{index .Config.Labels "company-agent.localization"}}'],
        capture_output=True, text=True,
    ).stdout.strip()
    if not server_only and web_revision != fingerprint():
        raise RuntimeError("Running web customization is outdated; run make up")
    from company_api import fingerprint as api_fingerprint
    for name in ("api", "worker", "worker_beat", "api_websocket"):
        container = compose(["ps", "-q", name], capture=True).stdout.strip()
        if not container:
            raise RuntimeError(f"Projects backend service is not running: {name}")
        revision = run(["docker", "inspect", container, "--format",
                        '{{index .Config.Labels "company-agent.projects"}}'],
                       capture_output=True, text=True).stdout.strip()
        if revision != api_fingerprint():
            raise RuntimeError(f"Projects backend customization is outdated: {name}; run make up")
    print("Dify projects backend check: current custom image")
    from model_stream import check as check_stream
    check_stream()
    # Capture the resolved config to validate bindings without printing credentials.
    resolved = json.loads(compose(["config", "--format", "json"], capture=True).stdout)
    sandbox_key = resolved["services"]["sandbox"]["environment"].get("API_KEY")
    for name in ("api", "worker", "worker_beat"):
        execution_key = resolved["services"][name]["environment"].get("CODE_EXECUTION_API_KEY")
        if not sandbox_key or execution_key != sandbox_key:
            raise RuntimeError(f"Sandbox authentication mismatch: {name}")
    print("Dify sandbox check: matching private credentials")
    for name, service in resolved["services"].items():
        for port in service.get("ports", []):
            allowed = settings()["DIFY_BIND_ADDRESS"] if name == "nginx" else "127.0.0.1"
            if port.get("host_ip") != allowed:
                raise RuntimeError(f"Unexpected port binding: {name}")
    compose(["ps"])
    address = settings()['DIFY_BIND_ADDRESS']
    probe_host = '127.0.0.1' if address == '0.0.0.0' else address
    if server_only:
        with local_open(f"http://{probe_host}:{settings()['DIFY_HTTP_PORT']}/console/api/ping", timeout=15) as response:
            if json.load(response).get('result') != 'pong':
                raise RuntimeError('Unexpected API health response')
        print('Kara API check: pong; client checks skipped')
        return
    url = f"http://{probe_host}:{settings()['DIFY_HTTP_PORT']}/install"
    try:
        with urllib.request.urlopen(url, timeout=15) as response:
            markup = response.read().decode("utf-8")
            class DocumentDirection(HTMLParser):
                attributes = {}
                def handle_starttag(self, tag, attrs):
                    if tag == "html":
                        self.attributes = dict(attrs)
            document = DocumentDirection()
            document.feed(markup)
            if document.attributes.get("lang") != "fa-IR" or document.attributes.get("dir") != "rtl":
                raise RuntimeError("Persian RTL web image is not active; run make up")
            print(f"Dify web check: HTTP {response.status}; {url}")
            print("Dify localization check: fa-IR / rtl")
        with urllib.request.urlopen(
            f"http://{probe_host}:{settings()['DIFY_HTTP_PORT']}/console/api/ping",
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
    parser.add_argument("--server-only", action="store_true", help="Skip all web/client checks in doctor")
    arguments = parser.parse_args()
    action = arguments.action
    if action == "setup":
        prepare()
    elif action == "up":
        prepare()
        compose(["config", "--quiet"])
        import company_api
        if not company_api.image_is_current():
            company_api.build_image()
        from persian_web import build_image, image_is_current
        if not image_is_current():
            print("Building the Persian web interface; pausing local services to free memory.", flush=True)
            compose(["stop"])
            try:
                build_image()
            except Exception:
                compose(["start"])
                raise
        compose(["up", "-d", "--quiet-pull"])
        wait_for_api()
        from model_stream import check as check_stream
        check_stream(apply=True)
        print(f"Dify: http://localhost:{settings()['DIFY_HTTP_PORT']}")
    elif action == "down":
        compose(["down"])
        print("Services stopped; local data preserved.")
    elif action == "status":
        compose(["ps"])
    elif action == "logs":
        compose(["logs", "--tail", "80", "api", "web", "worker"])
    else:
        doctor(server_only=arguments.server_only)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError, subprocess.CalledProcessError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
