#!/usr/bin/env python3
"""Build a Persian Dify image without modifying the pinned upstream checkout."""

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]
CUSTOM = ROOT / "infra/web"
SOURCE = ROOT / ".runtime/dify-web-source"
IMAGE = "company-agent/dify-web:1.17.1-fa"


def fingerprint():
    digest = hashlib.sha256((ROOT / "infra/dify.lock.json").read_bytes())
    for path in sorted(CUSTOM.rglob("*")):
        if path.is_file() and "node_modules" not in path.parts:
            digest.update(path.relative_to(CUSTOM).as_posix().encode())
            digest.update(path.read_bytes())
    digest.update(Path(__file__).read_bytes())
    return digest.hexdigest()


def image_is_current():
    result = subprocess.run(
        ["docker", "image", "inspect", IMAGE, "--format",
         '{{index .Config.Labels "company-agent.localization"}}'],
        capture_output=True, text=True,
    )
    return result.returncode == 0 and result.stdout.strip() == fingerprint()


def check_catalog(source):
    exceptions = json.loads((CUSTOM / "technical-values.json").read_text())
    count = 0
    for english_path in sorted((source / "web/i18n/en-US").glob("*.json")):
        english = json.loads(english_path.read_text())
        persian = json.loads((source / "web/i18n/fa-IR" / english_path.name).read_text())
        for key, original in english.items():
            assert key in persian, f"Missing Persian key: {english_path.stem}/{key}"
            translated = persian[key]
            assert type(original) is type(translated), f"Type mismatch: {key}"
            if isinstance(original, str):
                assert sorted(re.findall(r"{{.*?}}", original)) == sorted(
                    re.findall(r"{{.*?}}", translated)
                ), f"Interpolation mismatch: {key}"
                assert not original or translated, f"Empty translation: {key}"
                if re.search(r"[A-Za-z]{3}", translated) and not re.search(r"[\u0600-\u06ff]", translated):
                    assert exceptions.get(english_path.stem, {}).get(key) == translated, (
                        f"Untranslated interface text: {english_path.stem}/{key}"
                    )
            count += 1
    print(f"Persian catalog checked: {count} keys; placeholders and technical values preserved.")


def prepare_source():
    from local_dify import UPSTREAM, verify_checkout
    verify_checkout()
    if SOURCE.exists():
        shutil.rmtree(SOURCE)
    SOURCE.mkdir(parents=True, exist_ok=True)
    # Archive only tracked source. Private .env files, database volumes and .git never enter the build.
    paths = ["web", "packages", "package.json", "pnpm-lock.yaml", "pnpm-workspace.yaml",
             "e2e/package.json", "sdks/nodejs-client/package.json", "cli/package.json"]
    archive = subprocess.Popen(["git", "-C", str(UPSTREAM), "archive", "HEAD", *paths],
                               stdout=subprocess.PIPE)
    with tarfile.open(fileobj=archive.stdout, mode="r|") as files:
        files.extractall(SOURCE, filter="data")
    if archive.wait() != 0:
        raise RuntimeError("Unable to prepare the pinned web source")
    build_custom = SOURCE / ".company-web"
    shutil.copytree(CUSTOM, build_custom, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("node_modules"))
    environment = os.environ.copy()
    environment["GIT_CEILING_DIRECTORIES"] = str(SOURCE.parent)
    subprocess.run(["git", "apply", "--check", str(CUSTOM / "source.patch")],
                   cwd=SOURCE, env=environment, check=True)
    subprocess.run(["git", "apply", str(CUSTOM / "source.patch")],
                   cwd=SOURCE, env=environment, check=True)
    subprocess.run(["git", "apply", "--check", str(CUSTOM / "projects.patch")],
                   cwd=SOURCE, env=environment, check=True)
    subprocess.run(["git", "apply", str(CUSTOM / "projects.patch")],
                   cwd=SOURCE, env=environment, check=True)
    shutil.copytree(CUSTOM / "overlay", SOURCE / "web", dirs_exist_ok=True)
    overrides = json.loads((CUSTOM / "fa-overrides.json").read_text())
    for namespace, values in overrides.items():
        target = SOURCE / "web/i18n/fa-IR" / f"{namespace}.json"
        catalog = json.loads(target.read_text())
        assert values.keys() <= catalog.keys(), f"Unknown override in {namespace}"
        catalog.update(values)
        target.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n")
    shutil.copyfile(CUSTOM / "persian.css", SOURCE / "web/app/styles/persian.css")
    (SOURCE / ".dockerignore").write_text(
        "**/node_modules\n**/.next\n**/dist\n**/.git\n**/.env*\n**/__pycache__\n"
    )
    check_catalog(SOURCE)
    return SOURCE


def build_image():
    source = prepare_source()
    subprocess.run(["docker", "build", "--label",
                    f"company-agent.localization={fingerprint()}", "-t", IMAGE,
                    "-f", str(CUSTOM / "Dockerfile"), str(source)], check=True)


if __name__ == "__main__":
    prepare_source()
