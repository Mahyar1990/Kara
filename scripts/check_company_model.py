"""Probe a private chat-completions endpoint from the Dify plugin container."""

import argparse
import json
from pathlib import Path
import re
import ssl
import stat
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request


MAX_RESPONSE = 1024 * 1024
PRIVATE_CONFIG = ".runtime/company-model/connection.local.json"
DEFAULT_CONTAINER = "company-agent-local-plugin_daemon-1"


def validate_config(config):
    if not isinstance(config, dict):
        raise ValueError("invalid_config")
    for name in ("base_url", "model", "api_token"):
        value = config.get(name)
        if not isinstance(value, str) or not value.strip() or "\r" in value or "\n" in value:
            raise ValueError("invalid_config")
    url = urllib.parse.urlsplit(config["base_url"])
    if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError("invalid_endpoint")
    headers = config.get("extra_headers", {})
    if not isinstance(headers, dict):
        raise ValueError("invalid_headers")
    reserved = {"authorization", "host", "content-type", "content-length", "accept"}
    for name, value in headers.items():
        if not isinstance(name, str) or not re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+", name):
            raise ValueError("invalid_headers")
        if name.lower() in reserved or not isinstance(value, str) or "\r" in value or "\n" in value:
            raise ValueError("invalid_headers")
    return config


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def probe(config, timeout):
    """Return only safe metadata; never return response text or exception details."""
    validate_config(config)
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Authorization": "Bearer " + config["api_token"],
        **config.get("extra_headers", {}),
    }
    payload = {
        "model": config["model"],
        "messages": [{"role": "user", "content": "فقط عبارت «اتصال برقرار است» را بنویس."}],
    }
    request = urllib.request.Request(
        config["base_url"].rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST",
    )
    opener = urllib.request.build_opener(
        NoRedirect(), urllib.request.HTTPSHandler(context=ssl.create_default_context()),
    )
    try:
        with opener.open(request, timeout=timeout) as response:
            status = response.status
            body = response.read(MAX_RESPONSE + 1)
        if status != 200:
            return {"result": "http_error", "http_status": status}
        if len(body) > MAX_RESPONSE:
            return {"result": "invalid_response", "http_status": status}
        try:
            message = json.loads(body)["choices"][0]["message"]
            content = message["content"]
            if message.get("role") != "assistant" or not isinstance(content, str) or not content.strip():
                raise ValueError("invalid_response")
        except (ValueError, KeyError, IndexError, TypeError):
            return {"result": "invalid_response", "http_status": status}
        return {"result": "ok", "http_status": status, "assistant_chars": len(content)}
    except urllib.error.HTTPError as exc:
        return {"result": "http_error", "http_status": exc.code}
    except (TimeoutError, urllib.error.URLError) as exc:
        reason = getattr(exc, "reason", exc)
        if isinstance(reason, TimeoutError):
            return {"result": "timeout"}
        if isinstance(reason, ssl.SSLError):
            return {"result": "tls_error"}
        return {"result": "network_error"}
    except ssl.SSLError:
        return {"result": "tls_error"}
    except Exception:
        return {"result": "request_error"}


def load_private_config(path):
    root = Path(__file__).resolve().parent.parent
    path = path.resolve()
    path.relative_to(root)
    ignored = subprocess.run(
        ["git", "check-ignore", "-q", str(path)], cwd=root, capture_output=True,
    )
    if ignored.returncode != 0 or stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise ValueError("private_config_required")
    return validate_config(json.loads(path.read_text()))


def container_probe(config, container, timeout):
    # Credentials travel on stdin, never in Docker arguments or environment variables.
    result = subprocess.run(
        ["docker", "exec", "-i", container, "/usr/bin/python3", "-c",
         Path(__file__).read_text(), "--worker", "--timeout", str(timeout)],
        input=json.dumps(config), text=True, capture_output=True, timeout=timeout + 10,
    )
    if result.returncode:
        return {"result": "container_error"}
    try:
        report = json.loads(result.stdout)
        allowed = {"ok", "http_error", "invalid_response", "timeout", "tls_error", "network_error", "request_error"}
        if not isinstance(report, dict) or report.get("result") not in allowed:
            raise ValueError("invalid_report")
        safe = {"result": report["result"]}
        for key in ("http_status", "assistant_chars"):
            value = report.get(key)
            if type(value) is int and 0 <= value <= MAX_RESPONSE:
                safe[key] = value
        return safe
    except (ValueError, TypeError):
        return {"result": "container_error"}


def main():
    parser = argparse.ArgumentParser(description="بررسی خصوصی اتصال مدل از محیط افزونهٔ Dify")
    parser.add_argument("--config", type=Path, help="مسیر فایل خصوصی اتصال")
    parser.add_argument("--container", default=DEFAULT_CONTAINER, help="نام کانتینر افزونهٔ Dify")
    parser.add_argument("--timeout", type=int, choices=range(1, 61), default=20, metavar="1..60")
    parser.add_argument("--validate-only", action="store_true", help="فقط بررسی تنظیمات، بدون ارسال درخواست")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        try:
            report = probe(json.load(sys.stdin), args.timeout)
        except Exception:
            report = {"result": "request_error"}
        print(json.dumps(report))
        return 0
    try:
        root = Path(__file__).resolve().parent.parent
        config = load_private_config(args.config or root / PRIVATE_CONFIG)
    except Exception:
        print("خطا: فایل اتصال باید داخل پروژه، خارج از Git و با دسترسی خصوصی باشد؛ مقادیر اتصال نیز باید معتبر باشند.")
        return 2
    if args.validate_only:
        print("تنظیمات خصوصی معتبر است؛ هیچ درخواست شبکه‌ای ارسال نشد.")
        return 0
    try:
        report = container_probe(config, args.container, args.timeout)
    except subprocess.TimeoutExpired:
        report = {"result": "timeout"}
    except Exception:
        report = {"result": "container_error"}
    labels = {
        "ok": "پاسخ معتبر مدل دریافت شد",
        "http_error": "سرویس پاسخ HTTP ناموفق داد",
        "invalid_response": "قالب پاسخ با chat completions سازگار نبود",
        "timeout": "مهلت دریافت پاسخ تمام شد",
        "tls_error": "اعتبارسنجی اتصال امن ناموفق بود",
        "network_error": "دسترسی شبکه ناموفق بود",
        "request_error": "درخواست موفق نشد",
        "container_error": "اجرای بررسی در کانتینر افزونه موفق نشد",
    }
    print("نتیجهٔ اتصال: " + labels[report["result"]] + ".")
    if "http_status" in report:
        print("وضعیت HTTP:", report["http_status"])
    return 0 if report["result"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
