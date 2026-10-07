"""Collect private, read-only repository metadata for technical planning."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
ROLES = ("backend", "client", "newman", "playwright")
LABELS = {"backend": "بک‌اند", "client": "کلاینت", "newman": "تست Postman/Newman", "playwright": "تست Playwright"}
DEPENDENCIES = ("@nestjs/core", "express", "next", "react", "typescript", "axios", "redis",
                "react-query", "recoil", "newman", "@playwright/test", "playwright")
EVIDENCE = ("package.json", "package-lock.json", "README.md", "AGENTS.md", "tsconfig.json",
            "next.config.js", "nest-cli.json", "PROJECT_MAP.md", "src/index.ts", "src/main.ts", "pages/_app.tsx",
            "apps/clasor/src/main.ts", "apps/clasor/src/clasor.module.ts", "app/layout.tsx",
            "Dockerfile", "Dockerfile-dev", "Dockerfile-prod", "Dockerfile-sandbox",
            ".husky/pre-commit", "playwright.config.ts", "playwright.config.js")
LAYOUT = ("src", "apps", "pages", "app", "actions", "components", "hooks", "service", "store",
          "utils", "lib", "interface", "atom", "worker", "tests", "test", "e2e", "collections", "doc", "docs")
MAX_METADATA_BYTES = 10_000_000
MAX_COLLECTION_BYTES = 50_000_000


def git(root, *args, binary=False):
    env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}
    return subprocess.run(["git", "-c", "core.fsmonitor=false", *args], cwd=root, env=env,
                          capture_output=True, text=not binary, timeout=20)


def ref_snapshot(root, requested):
    if not re.fullmatch(r"[A-Za-z0-9_./-]{1,200}", requested) or requested.startswith("-"):
        raise ValueError("نام شاخه یا مرجع Git معتبر نیست")
    resolved = git(root, "rev-parse", "--verify", "--end-of-options", requested + "^{commit}")
    if resolved.returncode:
        raise ValueError("مرجع Git درخواست‌شده در نسخهٔ محلی مخزن موجود نیست؛ بررسی با شاخهٔ دیگری جایگزین نمی‌شود")
    commit = resolved.stdout.strip()
    # requested is validated above; --end-of-options is only consumed with --verify.
    symbolic = git(root, "rev-parse", "--symbolic-full-name", requested)
    tree = git(root, "ls-tree", "-r", "-z", commit, binary=True)
    if tree.returncode:
        raise ValueError("فهرست منابع نسخهٔ Git قابل خواندن نیست")
    objects = {}
    for entry in tree.stdout.split(b"\0"):
        if not entry:
            continue
        metadata, path = entry.split(b"\t", 1)
        mode, kind, oid = metadata.decode().split()
        if kind == "blob" and mode in ("100644", "100755"):
            objects[path.decode("utf-8", errors="replace")] = oid
    return commit, symbolic.stdout.strip() or requested, objects


def source_reader(root, objects=None):
    def read(relative, max_bytes=MAX_METADATA_BYTES):
        if objects is None:
            path = safe_file(root, relative, max_bytes)
            return path.read_bytes() if path else None
        oid = objects.get(relative)
        if not oid:
            return None
        size = git(root, "cat-file", "-s", oid)
        if size.returncode or int(size.stdout.strip()) > max_bytes:
            return None
        blob = git(root, "cat-file", "blob", oid, binary=True)
        if blob.returncode:
            raise ValueError("منبع نسخهٔ Git قابل خواندن نیست")
        return blob.stdout
    return read


def collection_metadata(read, paths):
    result = []
    for path in paths:
        if not path.endswith(".postman_collection.json"):
            continue
        contents = read(path, max_bytes=MAX_COLLECTION_BYTES)
        if contents is None:
            result.append({"path": path, "status": "unavailable_or_over_size_limit"})
            continue
        try:
            data = json.loads(contents)
        except (ValueError, UnicodeError):
            result.append({"path": path, "status": "invalid_format"})
            continue
        if not isinstance(data, dict) or not isinstance(data.get("item"), list):
            result.append({"path": path, "status": "invalid_format"})
            continue
        requests, tests = 0, 0
        pending = [data]
        while pending:
            item = pending.pop()
            if "request" in item:
                requests += 1
            tests += sum(event.get("listen") == "test" for event in item.get("event", []) if isinstance(event, dict))
            pending.extend(child for child in item.get("item", []) if isinstance(child, dict))
        result.append({"path": path, "status": "inspected", "sha256": hashlib.sha256(contents).hexdigest(),
                       "request_count": requests, "test_event_count": tests})
    return result


def safe_file(root, relative, max_bytes=MAX_METADATA_BYTES):
    path = root / relative
    if path.is_file() and path.resolve().is_relative_to(root) and path.stat().st_size <= max_bytes:
        return path
    return None


def semver(value):
    return value if isinstance(value, str) and re.fullmatch(r"[0-9A-Za-z.^~<>=|* +_-]{1,100}", value) else None


def inspect_repository(role, specification):
    location = specification.get("path")
    if not location:
        return {"status": "not_provided", "role": role, "execution_status": "not_run"}
    root = Path(location).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"پوشهٔ {LABELS[role]} در دسترس نیست")
    top = git(root, "rev-parse", "--show-toplevel")
    is_root = top.returncode == 0 and Path(top.stdout.strip()).resolve() == root
    requested = specification.get("ref")
    objects = None
    selected_commit = resolved_ref = None
    if requested:
        if not is_root:
            raise ValueError("برای بررسی شاخه، مسیر باید ریشهٔ همان مخزن Git باشد")
        selected_commit, resolved_ref, objects = ref_snapshot(root, requested)
    read = source_reader(root, objects)
    package_contents = read("package.json")
    package = json.loads(package_contents) if package_contents else {}
    groups = (package.get("dependencies", {}), package.get("devDependencies", {}))
    declared = {key: value for group in groups for key, value in group.items() if key in DEPENDENCIES}
    framework = "nextjs" if "next" in declared else "nestjs" if "@nestjs/core" in declared else "express" if "express" in declared else "unknown"
    if role == "playwright" and "@playwright/test" in declared:
        framework = "playwright"
    expected = specification.get("expected_framework")
    lock_contents = read("package-lock.json")
    lock = json.loads(lock_contents) if lock_contents else {}
    versions = {}
    for name, value in declared.items():
        resolved = lock.get("packages", {}).get("node_modules/" + name, {}).get("version")
        if not resolved:
            resolved = lock.get("dependencies", {}).get(name, {}).get("version")
        versions[name] = {"declared": semver(value), "locked": semver(resolved)}
    scripts = sorted(key for key in package.get("scripts", {}) if re.fullmatch(r"[A-Za-z][A-Za-z0-9:_-]{0,79}", key))
    evidence = []
    node_images = []
    for relative in EVIDENCE:
        contents = read(relative)
        if contents is None:
            continue
        evidence.append({"path": relative, "sha256": hashlib.sha256(contents).hexdigest()})
        if relative.startswith("Dockerfile"):
            # Retain Node tags only; registry addresses and other Docker contents stay out.
            for line in contents.decode("utf-8", errors="replace").splitlines():
                if re.match(r"\s*FROM\s", line):
                    node_images.extend({"path": relative, "node_tag": tag} for tag in
                                       re.findall(r"(?:^|/)node:([A-Za-z0-9_.-]+)", line))
    revision = git(root, "rev-parse", "HEAD") if is_root else None
    status = git(root, "status", "--porcelain=v1", "--untracked-files=normal") if is_root else None
    head = revision.stdout.strip() if revision and revision.returncode == 0 else None
    if head and not re.fullmatch(r"[0-9a-f]{40,64}", head):
        head = None
    git_status = {"repository_root": is_root, "head": selected_commit or head, "checkout_head": head,
                  "basis": "git_ref" if requested else "working_tree", "requested_ref": requested, "resolved_ref": resolved_ref,
                  "working_tree_modified": bool(status.stdout.strip()) if status and status.returncode == 0 else None}
    source_paths = list(objects) if objects is not None else [str(path.relative_to(root)) for path in root.glob("*.postman_collection.json")]
    collections = collection_metadata(read, source_paths) if role == "newman" else []
    if any(item["status"] == "inspected" for item in collections) and framework == "unknown":
        framework = "postman_collection"
    if objects is None:
        layout = [name for name in LAYOUT if (root / name).is_dir() and (root / name).resolve().is_relative_to(root)]
        test_count = None
    else:
        layout = [name for name in LAYOUT if any(path.startswith(name + "/") for path in objects)]
        test_count = sum(bool(re.search(r"\.(?:test|spec)\.[cm]?[jt]sx?$", path)) for path in objects)
    return {"status": "inspected", "role": role, "local_path": str(root),
            "observed_framework": framework, "expected_framework": expected,
            "framework_mismatch": bool(expected and expected != framework),
            "dependencies": versions, "script_names": scripts,
            "script_definitions_included": False,
            "node_versions_declared_in_docker": node_images,
            "node_engine_declared": semver(package.get("engines", {}).get("node")),
            "layout": layout, "test_file_count_by_convention": test_count, "postman_collections": collections,
            "evidence": evidence, "git": git_status, "scope": "root_package_and_selected_metadata",
            "execution_status": "not_run"}


def collect(mapping):
    product = mapping["product_id"]
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", product):
        raise ValueError("شناسهٔ محصول باید کوتاه و شامل حروف کوچک انگلیسی، عدد یا خط تیره باشد")
    repositories = {role: inspect_repository(role, mapping.get("repositories", {}).get(role, {})) for role in ROLES}
    issues = []
    for role, repository in repositories.items():
        if repository["status"] == "not_provided":
            issues.append({"role": role, "type": "repository_not_provided"})
        elif repository["framework_mismatch"]:
            issues.append({"role": role, "type": "framework_confirmation_required"})
        if repository.get("git", {}).get("working_tree_modified") and repository["git"]["basis"] == "working_tree":
            issues.append({"role": role, "type": "local_changes_not_in_head"})
        if any(item["status"] != "inspected" for item in repository.get("postman_collections", [])):
            issues.append({"role": role, "type": "postman_metadata_unavailable"})
    payload = {"schema_version": "1", "product_id": product, "repositories": repositories,
               "issues": issues, "technical_review_complete": False, "development_ready": False,
               "source_contents_included": False, "test_results_included": False}
    digest = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {**payload, "context_id": "context:" + digest,
            "collected_at": datetime.now(timezone.utc).isoformat()}


def render(context):
    lines = ["# زمینهٔ فنی محلی محصول " + context["product_id"], "",
             "این گزارش، اطلاعات اولیهٔ مخزنهاست. سورس، مقادیر تنظیمات و تعریف اسکریپت‌ها در آن کپی نشده‌اند.",
             "برنامه یا تست اجرا نشده و این گزارش مجوز شروع توسعه یا تأیید فنی ایجاد نمی‌کند.", "",
             "شناسهٔ زمینه: `" + context["context_id"] + "`", ""]
    for role, repository in context["repositories"].items():
        lines.extend(["## " + LABELS[role], ""])
        if repository["status"] == "not_provided":
            lines.extend(["مسیر هنوز ارائه نشده است.", ""])
            continue
        lines.extend(["- مسیر محلی: `" + repository["local_path"] + "`",
                      "- فناوری مشاهده‌شده در وابستگی مستقیم: `" + repository["observed_framework"] + "`",
                      "- نسخهٔ Git: `" + (repository["git"]["head"] or "نامشخص") + "`",
                      "- مبنای بررسی: `" + (repository["git"]["resolved_ref"] or "فایل‌های موجود در پوشه") + "`",
                      "- تغییر محلی: " + {True: "وجود دارد", False: "ندارد", None: "نامشخص"}[repository["git"]["working_tree_modified"]],
                      "- نام اسکریپت‌های تعریف‌شده: " + ("، ".join("`" + name + "`" for name in repository["script_names"]) or "ندارد"),
                      "- پوشه‌های ساختاری مشاهده‌شده: " + "، ".join(repository["layout"])])
        if repository["git"]["basis"] == "git_ref":
            lines.append("- اطلاعات از commit شاخه خوانده شده‌اند؛ نسخهٔ موجود در پوشه مبنای تحلیل نیست.")
        if repository["test_file_count_by_convention"] is not None:
            lines.append("- تعداد فایل‌های test/spec با نام‌گذاری رایج: " + str(repository["test_file_count_by_convention"]))
        for collection in repository["postman_collections"]:
            if collection["status"] == "inspected":
                lines.append("- مجموعهٔ Postman: `" + collection["path"] + "`؛ تعداد درخواست: " + str(collection["request_count"]) + "؛ رویداد تست: " + str(collection["test_event_count"]))
            else:
                lines.append("- مجموعهٔ Postman: `" + collection["path"] + "`؛ آمار قابل استخراج نبود؛ اندازه یا قالب فایل باید بررسی شود.")
        if repository["framework_mismatch"]:
            lines.append("- فناوری اعلام‌شده با وابستگی‌ها متفاوت است؛ تأیید مبنای صحیح توسط مالک محصول لازم است.")
        lines.extend(["", "| وابستگی | مقدار اعلام‌شده | نسخهٔ lock |", "|---|---|---|"])
        for name, version in repository["dependencies"].items():
            lines.append("| " + name + " | " + (version["declared"] or "نامشخص") + " | " + (version["locked"] or "نامشخص") + " |")
        lines.extend(["", "منابع ثبت‌شده: " + "، ".join("`" + item["path"] + "`" for item in repository["evidence"]), ""])
    lines.extend(["## موارد باقی‌مانده", "",
                  "- مطالعهٔ بخش‌های مرتبط سورس و مستندات برای درخواست مشخص و تعیین قرارداد API.",
                  "- روشن‌کردن اختلاف فناوری، مخزنهای ارائه‌نشده و تغییرات محلی، اگر گزارش شده‌اند.",
                  "- تعیین روش واقعی نصب، ساخت و تست با قواعد مخزن؛ نام یک اسکریپت شاهد اجرای آن نیست.",
                  "- بررسی مالک محصول و گفت‌وگو با TL و توسعه‌دهنده پیش از تحویل اجرایی.", ""])
    return "\n".join(lines)


def write_private(mapping, context):
    folder = ROOT / ".runtime/products" / context["product_id"]
    files = {"sources.local.json": json.dumps(mapping, ensure_ascii=False, indent=2) + "\n",
             "technical-context.local.json": json.dumps(context, ensure_ascii=False, indent=2) + "\n",
             "technical-context.local.md": render(context)}
    for name in files:
        result = git(ROOT, "check-ignore", "-q", str(folder / name))
        if result.returncode != 0:
            raise ValueError("محل فایل خصوصی باید پیش از ذخیره در گیت نادیده گرفته شود")
    for directory in (ROOT / ".runtime", ROOT / ".runtime/products", folder):
        if directory.is_symlink():
            raise ValueError("پوشهٔ خروجی خصوصی نباید پیوند نمادین باشد")
        directory.mkdir(mode=0o700, exist_ok=True)
    os.chmod(folder.parent, 0o700)
    os.chmod(folder, 0o700)
    for name, content in files.items():
        with tempfile.NamedTemporaryFile(mode="w", dir=folder, encoding="utf-8", delete=False) as stream:
            temporary = Path(stream.name)
            try:
                os.chmod(temporary, 0o600)
                stream.write(content)
            except BaseException:
                temporary.unlink(missing_ok=True)
                raise
        os.replace(temporary, folder / name)
    return folder


def main():
    parser = argparse.ArgumentParser(description="آماده‌سازی خصوصی زمینهٔ فنی، بدون تغییر سورس یا اجرای پروژه")
    parser.add_argument("--product", required=True)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--ref", help="شاخه یا مرجع مشترک مخزنها؛ پیش‌فرض کلاسور origin/sandbox است")
    for role in ROLES:
        parser.add_argument("--" + role)
    parser.add_argument("--expected-backend", choices=("nestjs", "express"))
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", args.product):
        parser.error("شناسهٔ محصول معتبر نیست")
    if args.refresh:
        mapping = json.loads((ROOT / ".runtime/products" / args.product / "sources.local.json").read_text())
        if mapping["product_id"] != args.product:
            parser.error("شناسهٔ محصول با تنظیم خصوصی مطابق نیست")
    else:
        mapping = {"product_id": args.product, "repositories": {}}
    for role in ROLES:
        if getattr(args, role):
            mapping["repositories"][role] = {"path": str(Path(getattr(args, role)).expanduser().resolve())}
    if args.expected_backend:
        mapping["repositories"].setdefault("backend", {})["expected_framework"] = args.expected_backend
    for specification in mapping["repositories"].values():
        if specification.get("path"):
            if args.ref:
                specification["ref"] = args.ref
            elif args.product == "klassor":
                specification.setdefault("ref", "origin/sandbox")
    if not any(item.get("path") for item in mapping["repositories"].values()):
        parser.error("حداقل یک مسیر مخزن لازم است")
    context = collect(mapping)
    folder = write_private(mapping, context)
    print("زمینهٔ اولیهٔ خصوصی ذخیره شد:", folder)
    for role, repository in context["repositories"].items():
        print(LABELS[role] + ":", repository.get("observed_framework", "ارائه نشده"))
    print("برنامه و تست محصول اجرا نشده‌اند؛ موارد نیازمند بررسی در اطلاعات اولیه:", len(context["issues"]))


if __name__ == "__main__":
    main()
