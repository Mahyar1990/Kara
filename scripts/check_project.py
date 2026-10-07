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
    web = ROOT / "infra/web"
    package = json.loads((web / "package.json").read_text())
    package_lock = json.loads((web / "package-lock.json").read_text())
    assert package["dependencies"] == package_lock["packages"][""]["dependencies"]
    for filename in ("fa-overrides.json", "literal-translations.json", "technical-values.json"):
        json.loads((web / filename).read_text())
    for namespace, messages in json.loads((web / "fa-overrides.json").read_text()).items():
        assert namespace and messages
        assert all(isinstance(v, str) and re.search(r"[\u0600-\u06ff]", v) for v in messages.values())
    for message in json.loads((web / "literal-translations.json").read_text()).values():
        assert re.search(r"[\u0600-\u06ff]", message), "Interface literal must be Persian"
    shared = subprocess.run(
        ["git", "check-ignore", "--quiet", "infra/compose.local.yaml"], cwd=ROOT,
    )
    assert shared.returncode == 1, "Shared Compose configuration must not be ignored"
    examples = list((ROOT / "fixtures/requirements").glob("*.json"))
    assert len(examples) == 3, "Three requirement fixtures are required"
    for path in examples:
        sample = json.loads(path.read_text())
        assert sample["synthetic"] is True and sample["jira_key"] is None
        assert sample["product"] == "کلاسور" and sample["request"]
        assert sample["expected"]["po_decision"] == "unreviewed"
    for name in ("requirement-analyst.md", "technical-planner.md"):
        assert len((ROOT / "prompts" / name).read_text()) > 1000
    for path in [ROOT / "README.md", ROOT / "CONTRIBUTING.md", *list((ROOT / "docs").glob("*.md")),
                 *list((ROOT / "workflows").rglob("*.md"))]:
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
    print("Project checks passed: pinned version, fixtures, prompts, links and Git exclusions.")


if __name__ == "__main__":
    main()
