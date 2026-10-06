#!/usr/bin/env python3
"""Check portable project content without requiring Docker or private settings."""

import ast
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    for script in (ROOT / "scripts").glob("*.py"):
        ast.parse(script.read_text(), filename=str(script))
    lock = json.loads((ROOT / "infra/dify.lock.json").read_text())
    assert re.fullmatch(r"[a-f0-9]{40}", lock["commit"]), "Dify commit must be pinned"
    assert (ROOT / "infra/compose.local.yaml").is_file(), "Local Compose configuration is required"
    shared = subprocess.run(
        ["git", "check-ignore", "--quiet", "infra/compose.local.yaml"], cwd=ROOT,
    )
    assert shared.returncode == 1, "Shared Compose configuration must not be ignored"
    for path in [ROOT / "README.md", ROOT / "CONTRIBUTING.md", *list((ROOT / "docs").glob("*.md"))]:
        text = path.read_text()
        assert text.count("```") % 2 == 0, f"Unclosed code fence: {path}"
        for link in re.findall(r"\]\(([^)]+)\)", text):
            if "://" in link or link.startswith("#"):
                continue
            target = link.split("#")[0]
            assert not target.startswith("/"), f"Non-portable local link: {path}"
            assert (path.parent / target).exists(), f"Missing link target: {path}: {target}"
    for private_path in (".env.local", ".runtime/private-file"):
        ignored = subprocess.run(
            ["git", "check-ignore", "--quiet", private_path], cwd=ROOT,
        )
        assert ignored.returncode == 0, "Private runtime files must be ignored"
    tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, check=True,
                             capture_output=True, text=True).stdout.splitlines()
    assert not any(p.startswith(".runtime/") or p == ".env.local" for p in tracked)
    print("Project checks passed: pinned Dify, platform content, links and Git exclusions.")


if __name__ == "__main__":
    main()
