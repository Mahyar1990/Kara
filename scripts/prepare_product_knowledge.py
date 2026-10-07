"""Read repository guidance and technical docs from the pinned product snapshots.

The catalog stays local. It is not an approval, an exhaustive secret scanner, or
an upload to a model. Skills are cataloged for selective use, never executed.
"""

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from urllib.parse import urlsplit

import prepare_product_context as metadata

MAX_DOCUMENT_BYTES = 2_000_000
MAX_CATALOG_BYTES = 25_000_000
CORE = ("AGENTS.md", "PROJECT_MAP.md")
TEXT_EXTENSIONS = (".md", ".mdx", ".txt")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def candidate(path):
    return (path in CORE or path.startswith(("doc/", "docs/", ".agents/skills/"))
            or path == ".specify/memory/constitution.md")


def kind(path):
    if path == "AGENTS.md":
        return "repository_policy"
    if path == "PROJECT_MAP.md":
        return "project_map"
    if path.startswith(".agents/skills/"):
        return "workflow" if path.endswith("/SKILL.md") else "workflow_reference"
    if path == ".specify/memory/constitution.md":
        return "repository_constitution"
    return "documentation"


def redact(text):
    counts = Counter()
    if re.search(r"-----BEGIN (?:[A-Z ]*PRIVATE KEY|CERTIFICATE)-----", text):
        return None, {"key_or_certificate_material": 1}

    def replace(label, expression, replacement):
        nonlocal text
        text, number = re.subn(expression, replacement, text)
        counts[label] += number

    # Keep configuration names and placeholders. Never copy literal credentials.
    replace("bearer", r"(?i)\bBearer[ \t]+[A-Za-z0-9_+./=-]{8,}", "Bearer [REDACTED]")
    names = r"(?:api[_-]?token|api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|password|authorization|cookie)"
    replace("credential_literal", r"(?i)([\"']?" + names + r"[\"']?\s*[:=]\s*)([\"'])([^\r\n]*?)\2",
            lambda m: m[1] + m[2] + "[REDACTED]" + m[2])
    replace("credential_assignment", r"(?im)^(\s*(?:export\s+)?" + names + r"\s*=\s*)([^\r\n]+)$",
            lambda m: m[1] + "[REDACTED]")

    def url(match):
        try:
            parts = urlsplit(match[0])
        except ValueError:
            return "https://[HOST]"
        return parts.scheme + "://[HOST]" + parts.path + ("?[REDACTED]" if parts.query else "")

    replace("url_host_and_query", r"https?://[^\s<>\"'`)]+", url)
    return text, {key: value for key, value in counts.items() if value}


def collect_knowledge(mapping, context):
    if mapping["product_id"] != context["product_id"]:
        raise ValueError("شناسهٔ محصول در تنظیم و گزارش یکسان نیست")
    sources, repositories, issues = [], {}, []
    total = 0
    for role in ("backend", "client"):
        repo = context["repositories"][role]
        if repo["status"] != "inspected" or repo["git"]["basis"] != "git_ref":
            raise ValueError("گزارش نسخهٔ مشخص Git برای بک‌اند و کلاینت لازم است")
        root = Path(mapping["repositories"][role]["path"]).resolve()
        if str(root) != repo["local_path"]:
            raise ValueError("مسیر مخزن تغییر کرده؛ گزارش زمینهٔ فنی ابتدا به‌روز شود")
        top = metadata.git(root, "rev-parse", "--show-toplevel")
        if top.returncode or Path(top.stdout.strip()).resolve() != root:
            raise ValueError("مسیر، ریشهٔ مخزن Git نیست")
        commit, _, objects = metadata.ref_snapshot(root, repo["git"]["head"])
        read = metadata.source_reader(root, objects)
        repositories[role] = {"commit": commit, "ref": repo["git"]["resolved_ref"],
                              "documentation_roots": [name for name in ("doc", "docs") if any(p.startswith(name + "/") for p in objects)]}
        for required in CORE:
            if required not in objects:
                issues.append({"role": role, "path": required, "type": "required_source_missing"})
        # Root policies come first so a large doc tree cannot consume their budget.
        paths = sorted((p for p in objects if candidate(p)), key=lambda p: (p not in CORE, p))
        for path in paths:
            source = {"id": role + ":" + path, "role": role, "path": path, "commit": commit,
                      "git_blob": objects[path], "kind": kind(path)}
            if PurePosixPath(path).suffix.lower() not in TEXT_EXTENSIONS:
                source["status"] = "indexed_without_text"
            else:
                data = read(path, max_bytes=MAX_DOCUMENT_BYTES)
                if data is None:
                    source["status"] = "over_size_limit_or_unavailable"
                elif total + len(data) > MAX_CATALOG_BYTES:
                    source["status"] = "catalog_size_limit"
                else:
                    total += len(data)
                    source["sha256"] = hashlib.sha256(data).hexdigest()
                    try:
                        text = data.decode("utf-8-sig")
                    except UnicodeError:
                        source["status"] = "unsupported_encoding"
                    else:
                        cleaned, redactions = redact(text)
                        source["redactions"] = redactions
                        if cleaned is None:
                            source["status"] = "blocked_key_material"
                        else:
                            source.update(status="available", content=cleaned,
                                          content_sha256=hashlib.sha256(cleaned.encode()).hexdigest(),
                                          title=next((line.lstrip("# ") for line in cleaned.splitlines() if line.startswith("# ")), PurePosixPath(path).name),
                                          headings=[line.strip() for line in cleaned.splitlines() if re.match(r"^#{1,6} ", line)])
            if source["status"] != "available":
                issues.append({"role": role, "path": path, "type": source["status"]})
            sources.append(source)
    payload = {"schema_version": "1", "product_id": mapping["product_id"],
               "technical_context_id": context["context_id"], "repositories": repositories,
               "sources": sources, "issues": issues, "local_only": True,
               "human_data_review_required": True, "source_code_inspected": False,
               "technical_review_complete": False, "development_ready": False}
    return {**payload, "knowledge_id": "knowledge:" + digest(payload),
            "collected_at": datetime.now(timezone.utc).isoformat()}


def summary(catalog):
    lines = ["# منابع دانش محصول", "", "شناسه: `" + catalog["knowledge_id"] + "`", "",
             "این بسته فقط محلی است. پالایش خودکار جای بررسی انسانی پیش از ارسال به مدل را نمی‌گیرد.",
             "متن مستندات، تأیید صحت پیاده‌سازی، موفقیت تست یا اجازهٔ توسعه ایجاد نمی‌کند.", ""]
    for role, repo in catalog["repositories"].items():
        selected = [s for s in catalog["sources"] if s["role"] == role]
        counts = Counter(s["kind"] for s in selected if s["status"] == "available")
        lines.extend(["## " + metadata.LABELS[role], "", "- مرجع: `" + repo["ref"] + "`",
                      "- نسخه: `" + repo["commit"] + "`",
                      "- پوشهٔ مستندات: " + "، ".join(repo["documentation_roots"]),
                      "- تعداد منابع دارای متن: " + str(sum(counts.values())),
                      "- تعداد مستندات دارای متن: " + str(counts["documentation"]), ""])
    lines.extend(["## فهرست منابع", "", "| شناسه | نوع | وضعیت |", "|---|---|---|"])
    for source in catalog["sources"]:
        lines.append("| " + source["id"].replace("|", "\\|") + " | " + source["kind"] + " | " + source["status"] + " |")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="تهیهٔ خصوصی دانش مخزن از همان نسخهٔ زمینهٔ فنی")
    parser.add_argument("--product", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", args.product):
        parser.error("شناسهٔ محصول معتبر نیست")
    folder = metadata.ROOT / ".runtime/products" / args.product
    mapping = json.loads((folder / "sources.local.json").read_text())
    context = json.loads((folder / "technical-context.local.json").read_text())
    catalog = collect_knowledge(mapping, context)
    metadata.write_private_files(args.product, {"knowledge-catalog.local.json": json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
                                                "knowledge-summary.local.md": summary(catalog)})
    print("منابع دانش، بدون ارسال به مدل، به‌صورت خصوصی ثبت شدند.")
    for role in catalog["repositories"]:
        counts = Counter(s["status"] for s in catalog["sources"] if s["role"] == role)
        print(metadata.LABELS[role], dict(counts))


if __name__ == "__main__":
    main()
