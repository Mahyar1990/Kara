#!/usr/bin/env python3
"""Validate portable planning artifacts; does not prove semantic or runtime acceptance."""

import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (
    "spec.md", "plan.md", "research.md", "data-model.md", "contracts/interface.md",
    "quickstart.md", "tasks.md", "execution.md", "checklists/requirements.md",
    "checklists/review.md",
)


def check():
    lock = json.loads((ROOT / "infra/spec-kit.lock.json").read_text())
    assert re.fullmatch(r"[a-f0-9]{40}", lock["commit"]), "Pin the exact Spec Kit source"
    assert lock["integration"] == "codex" and lock["git_extension"] is False
    for manifest in (ROOT / ".specify/integrations").glob("*.manifest.json"):
        data = json.loads(manifest.read_text())
        assert data["version"] == lock["version"]
        for name, digest in data["files"].items():
            assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, name
    assert not (ROOT / ".specify/extensions/git").exists(), "Keep current branch policy"
    for script in (ROOT / ".specify/scripts/bash").glob("*.sh"):
        subprocess.run(["bash", "-n", str(script)], check=True)
    subprocess.run(["bash", "-n", str(ROOT / "scripts/spec-kit.sh")], check=True)
    features = sorted(p for p in (ROOT / "specs").glob("[0-9]*") if p.is_dir())
    numbers = [int(p.name.split("-")[0]) for p in features]
    assert all(numbers.count(n) == 1 for n in range(2, 11)), "KP-02..10 must each exist once"
    total_fr = total_tasks = 0
    for feature in features:
        for name in REQUIRED:
            assert (feature / name).is_file(), f"Missing {feature.name}/{name}"
        spec = (feature / "spec.md").read_text()
        tasks = (feature / "tasks.md").read_text()
        requirements = re.findall(r"^- \*\*(FR-\d{3})\*\*", spec, re.M)
        assert requirements and len(requirements) == len(set(requirements)), feature.name
        task_rows = re.findall(r"^- \[[ xX]\] (T\d{3}) (.+)$", tasks, re.M)
        ids = [row[0] for row in task_rows]
        assert ids == [f"T{n:03}" for n in range(1, len(ids) + 1)], feature.name
        for task_id, description in task_rows:
            assert "`" in description, f"Task requires a concrete path: {feature.name}/{task_id}"
        for requirement in requirements:
            row = re.search(rf"^\| {requirement} \| (US\d+) \| ([^|]+)\|$", tasks, re.M)
            assert row, f"Unmapped {feature.name}/{requirement}"
            mapped = re.findall(r"T\d{3}", row[2])
            assert mapped and set(mapped) <= set(ids), row[0]
        for marker in ("User Scenarios & Testing", "Requirements", "Success Criteria", "Assumptions"):
            assert marker in spec, f"{feature.name}: {marker}"
        for marker in ("NEEDS CLARIFICATION", "[FEATURE NAME]", "[DATE]", "$ARGUMENTS"):
            assert marker not in spec, f"Unresolved scaffold: {feature.name}: {marker}"
        total_fr += len(requirements)
        total_tasks += len(ids)
    for path in [*(ROOT / "specs").rglob("*.md"), ROOT / ".specify/memory/constitution.md"]:
        content = path.read_text()
        assert content.count("```") % 2 == 0, f"Unclosed fence: {path}"
        for target in re.findall(r"\]\(([^)]+)\)", content):
            if "://" in target or target.startswith("#"):
                continue
            target = target.split("#")[0]
            assert not target.startswith("/"), f"Non-portable link: {path}"
            assert (path.parent / target).exists(), f"Missing target: {path}: {target}"
    print(f"Spec structure passed: {len(features)} features, {total_fr} FRs, {total_tasks} tasks; "
          "links, task mappings, shell syntax and upstream manifests valid. "
          "Semantic review and runtime acceptance are separate.")


if __name__ == "__main__":
    check()
