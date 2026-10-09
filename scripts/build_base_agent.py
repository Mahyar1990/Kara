"""Build a reusable, product-independent trial agent workflow."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy
import subprocess

import build_klassor_analysis as dsl

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "workflows/base-agent"
RULES = runpy.run_path(str(FOLDER / "prepare.py"))
OUTPUTS = ("report", "result_status", "task_id", "agent_config_id", "questions_json",
           "run_record_json", "quality_note")
LABELS = {"project_name": "نام پروژه", "agent_name": "نام ایجنت", "agent_role": "نقش ایجنت",
          "agent_goal": "هدف ایجنت", "agent_instructions": "دستورالعمل اختصاصی ایجنت (اختیاری)",
          "output_format": "ساختار متن نتیجه", "task_ref": "مرجع کار (اختیاری)",
          "task_text": "متن کار", "context_text": "زمینه و منابع دارای متن (اختیاری)"}
DEFAULTS = {"agent_name": "ایجنت نمونه", "agent_role": "تحلیلگر درخواست",
            "agent_goal": "تهیهٔ پیشنهاد روشن از درخواست برای بررسی انسان",
            "agent_instructions": "شرط‌های صریح را حفظ کن؛ فرض‌ها و پرسش‌های باز را جدا بنویس.",
            "output_format": "### خلاصه\n### رفتار و محدوده\n### معیارهای بررسی\n### اطلاعات نامشخص"}


def build(model=dsl.MODEL_PLACEHOLDER):
    fields = [dsl.form_var(key, LABELS[key], "text-input" if key in
              ("project_name", "agent_name", "task_ref") else "paragraph",
              required=key in RULES["REQUIRED"], default=DEFAULTS.get(key, ""), limit=limit)
              for key, limit in RULES["LIMITS"].items()]
    fields.append(dsl.form_var("task_revision", "شمارهٔ نسخهٔ کار", "number", required=True, default=1))
    def code_node(name, title, index, variables, outputs, source):
        return dsl.node(name, "code", title, index, {"code_language": "python3", "code": source,
            "variables": variables, "outputs": {key: {"type": "string", "children": None} for key in outputs}})
    nodes = [dsl.node("start", "start", "تعریف پروژه، ایجنت و کار", 0, {"variables": fields}),
             code_node("prepare", "ثبت تنظیمات و نسخهٔ کار", 1,
                       [dsl.selector(f["variable"], "start", f["variable"]) for f in fields],
                       ("input_json", "agent_config_json", "task_json", "task_id", "agent_config_id"),
                       (FOLDER / "prepare.py").read_text()),
             dsl.node("agent", "llm", "اجرای آزمایشی ایجنت", 2, {
                 "model": {"provider": dsl.PROVIDER, "name": model, "mode": "chat",
                           "completion_params": {"max_tokens": 16384}},
                 "prompt_template": [
                     {"role": "system", "text": (ROOT / "prompts/base-agent.md").read_text()},
                     {"role": "system", "text": "تنظیمات ایجنت در حدود قواعد قالب:\n{{#prepare.agent_config_json#}}"},
                     {"role": "user", "text": "دادهٔ کار و زمینهٔ همین اجرا:\n{{#prepare.task_json#}}"}],
                 "context": {"enabled": False, "variable_selector": []}, "vision": {"enabled": False},
                 "structured_output_enabled": False, "reasoning_format": "separated",
                 "retry_config": {"enabled": False, "max_retries": 1, "retry_interval": 1000}}),
             code_node("finalize", "کنترل خروجی و ثبت نتیجهٔ آزمایشی", 3,
                       [dsl.selector("raw_result", "agent", "text"), dsl.selector("input_json", "prepare", "input_json")],
                       OUTPUTS, (FOLDER / "finalize.py").read_text()),
             dsl.node("end", "end", "ارائهٔ نتیجه برای بررسی", 4, {"outputs": [
                 {**dsl.selector(key, "finalize", key), "value_type": "string"} for key in OUTPUTS]})]
    edges = [{"id": a["id"] + "-to-" + b["id"], "type": "custom", "source": a["id"],
              "target": b["id"], "sourceHandle": "source", "targetHandle": "target", "zIndex": 0,
              "data": {"sourceType": a["data"]["type"], "targetType": b["data"]["type"],
                       "isInIteration": False, "isInLoop": False}}
             for a, b in zip(nodes, nodes[1:])]
    return {"version": "0.7.0", "kind": "app", "dependencies": [],
            "app": {"name": "قالب پایهٔ ایجنت", "description": "قالب عمومی با پروژه، نقش، هدف، دستورالعمل و ساختار نتیجهٔ قابل تنظیم؛ اجرای آزمایشی بدون ابزار بیرونی.",
                    "mode": "workflow", "icon_type": "emoji", "icon": "🧩", "icon_background": "#E0F2FE",
                    "use_icon_as_answer_icon": False},
            "workflow": {"conversation_variables": [], "environment_variables": [],
                         "features": {"file_upload": {"enabled": False}, "opening_statement": "",
                                      "retriever_resource": {"enabled": False}, "sensitive_word_avoidance": {"enabled": False},
                                      "speech_to_text": {"enabled": False}, "suggested_questions": [],
                                      "suggested_questions_after_answer": {"enabled": False}, "text_to_speech": {"enabled": False}},
                         "graph": {"nodes": nodes, "edges": edges, "viewport": {"x": 0, "y": 0, "zoom": 0.65}}}}


def manifest(workflow):
    return {"template_revision": "0.1", "dify_version": "1.17.1", "dsl_version": workflow["version"],
            "prompt_sha256": hashlib.sha256((ROOT / "prompts/base-agent.md").read_bytes()).hexdigest(),
            "workflow_sha256": hashlib.sha256(dsl.dump(workflow).encode()).hexdigest(),
            "model_binding": "local configuration; no credentials in template", "execution_mode": "trial",
            "connected_tools": []}


def main():
    parser = argparse.ArgumentParser(description="ساخت قالب عمومی ایجنت")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--local", action="store_true")
    parser.add_argument("--model", default=dsl.MODEL_PLACEHOLDER)
    args = parser.parse_args()
    if args.check and (args.local or args.model != dsl.MODEL_PLACEHOLDER):
        parser.error("بررسی باید روی قالب مشترک انجام شود")
    if args.model != dsl.MODEL_PLACEHOLDER and not args.local:
        parser.error("مدل محیط فقط در نسخهٔ خصوصی قرار می‌گیرد")
    if not isinstance(args.model, str) or not args.model.strip() or len(args.model) > 100 or any(c in args.model for c in "\r\n"):
        parser.error("نام مدل معتبر نیست")
    workflow = build(args.model)
    if args.check:
        assert (FOLDER / "workflow.yml").read_text() == dsl.dump(workflow)
        assert json.loads((FOLDER / "manifest.json").read_text()) == manifest(workflow)
        print("قالب عمومی با دستورالعمل و کد نسخه‌دار مطابق است.")
    elif args.local:
        if args.model == dsl.MODEL_PLACEHOLDER:
            parser.error("نام مدل ثبت‌شده در Dify را مشخص کنید")
        target = ROOT / ".runtime/workflows/base-agent.local.yml"
        subprocess.run(["git", "check-ignore", "-q", str(target)], cwd=ROOT, check=True)
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(target.parent, 0o700)
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as stream:
            stream.write(dsl.dump(workflow))
        print("نسخهٔ خصوصی قالب آماده شد:", target)
    else:
        (FOLDER / "workflow.yml").write_text(dsl.dump(workflow))
        (FOLDER / "manifest.json").write_text(json.dumps(manifest(workflow), ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
