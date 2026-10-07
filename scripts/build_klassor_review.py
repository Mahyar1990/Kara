"""Compose the existing analyst and Dify's native human review form."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import runpy
import subprocess
import uuid

import build_klassor_analysis as analysis

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "workflows/klassor-review"
RULES = runpy.run_path(str(FOLDER / "decision.py"))
WEB_DELIVERY_ID = str(uuid.uuid5(uuid.NAMESPACE_URL, "company-agent/klassor-review/web"))
OUTPUTS = ["report", "requirement", "analysis_ref", "human_decision", "decision_record_json",
           "next_analysis_inputs_json", "revision_proposal", "next_step"]
FORM = """# بررسی و تصمیم مالک محصول

شناسهٔ نسخهٔ در حال بررسی: `{{#review_prepare.analysis_ref#}}`

## درخواست و منابع

{{#review_prepare.request_display#}}

## پیش‌نویس تحلیل

{{#review_prepare.original_report#}}

## متن نهایی نیازمندی

بخش‌های ۲ تا ۹ را بررسی و در صورت نیاز اصلاح کنید. مشخصات نسخه و تصمیم را بستر ثبت می‌کند؛ تغییر متن، نسخهٔ تازه می‌سازد.

{{#$output.reviewed_body#}}

### نام مالک محصول

{{#$output.reviewer#}}

### نتیجهٔ بررسی معیارها و پرسش‌های باز

{{#$output.assessment#}}

### توضیح تصمیم، پاسخ پرسش‌ها یا اصلاح لازم

برای درخواست اصلاح یا رد، توضیح لازم است.

{{#$output.notes#}}

تأیید فقط به همین متن و نسخه تعلق دارد. تصمیم نمونهٔ آزمایشی مجوز واقعی تحویل ایجاد نمی‌کند.
"""


def code_node(name, title, index, wrapper, variables, outputs):
    return analysis.node(name, "code", title, index, {
        "code_language": "python3", "code": (FOLDER / "decision.py").read_text() + "\n\n" + wrapper,
        "variables": variables,
        "outputs": {key: {"type": kind, "children": None} for key, kind in outputs.items()},
    })


def edge(source, target, handle="source"):
    return {"id": source["id"] + "-" + handle + "-to-" + target["id"], "type": "custom",
            "source": source["id"], "sourceHandle": handle, "target": target["id"], "targetHandle": "target",
            "zIndex": 0, "data": {"sourceType": source["data"]["type"], "targetType": target["data"]["type"],
                                  "isInIteration": False, "isInLoop": False}}


def build(harness=False):
    workflow = analysis.build()
    nodes = workflow["workflow"]["graph"]["nodes"][:-1]
    if harness:
        nodes = nodes[:2]
        nodes[0]["data"]["variables"].append(analysis.form_var(
            "existing_report", "تحلیل ساختگی برای آزمون فرم", "paragraph", required=True, limit=120000))
    fields = [analysis.form_var("reviewer_name", "نام مالک محصول", "text-input", required=True, limit=100),
              analysis.form_var("review_kind", "نوع درخواست", "select", required=True, default=RULES["TRIAL"])]
    fields[-1]["options"] = [RULES["TRIAL"]] if harness else [RULES["TRIAL"], RULES["LOCAL"]]
    nodes[0]["data"]["variables"].extend(fields)
    report_source = ("start", "existing_report") if harness else ("finalize", "report")
    prepared = code_node("review_prepare", "آماده‌سازی فرم بررسی", len(nodes),
        "def main(input_json, report, reviewer_name, review_kind):\n"
        "    return prepare_review(input_json, report, reviewer_name, review_kind)\n", [
            analysis.selector("input_json", "prepare", "input_json"),
            analysis.selector("report", *report_source),
            analysis.selector("reviewer_name", "start", "reviewer_name"),
            analysis.selector("review_kind", "start", "review_kind"),
        ], {"context_json": "string", "reviewed_body": "string", "original_report": "string",
            "request_display": "string", "reviewer_options": "array[string]", "analysis_ref": "string"})
    human = analysis.node("human_review", "human-input", "بررسی و تصمیم مالک محصول", len(nodes) + 1, {
        "delivery_methods": [{"id": WEB_DELIVERY_ID, "type": "webapp", "enabled": True, "config": {}}],
        "form_content": FORM,
        "inputs": [
            {"type": "paragraph", "output_variable_name": "reviewed_body", "default": {
                "type": "variable", "selector": ["review_prepare", "reviewed_body"], "value": ""}},
            {"type": "select", "output_variable_name": "reviewer", "option_source": {
                "type": "variable", "selector": ["review_prepare", "reviewer_options"], "value": []}},
            {"type": "select", "output_variable_name": "assessment", "option_source": {
                "type": "constant", "selector": [], "value": [RULES["READY"], RULES["NOT_READY"]]}},
            {"type": "paragraph", "output_variable_name": "notes", "default": {
                "type": "constant", "selector": [], "value": ""}},
        ],
        "user_actions": [{"id": action, "title": title, "button_style": style} for action, title, style in [
            ("approve", "تأیید این نسخه", "primary"),
            ("request_changes", "درخواست اصلاح", "default"), ("reject", "رد درخواست", "ghost")]],
        "timeout": 3, "timeout_unit": "day",
    })
    edges = [edge(source, target) for source, target in zip(nodes, nodes[1:])]
    edges.extend([edge(nodes[-1], prepared), edge(prepared, human)])
    nodes.extend([prepared, human])
    branch_column = len(nodes)
    for index, (action, title) in enumerate([
        ("approve", "ثبت تأیید نسخه"), ("request_changes", "ثبت اصلاح و ورودی بازتحلیل"),
        ("reject", "ثبت رد درخواست"), ("timeout", "ثبت پایان مهلت بررسی"),
    ]):
        variables = [analysis.selector("context_json", "review_prepare", "context_json")]
        if action == "timeout":
            wrapper = 'def main(context_json):\n    return {"result_json": json.dumps(record_decision(context_json, "timeout"), ensure_ascii=False)}\n'
        else:
            variables.extend(analysis.selector(name, "human_review", name)
                             for name in ["reviewer", "assessment", "reviewed_body", "notes"])
            wrapper = ('def main(context_json, reviewer, assessment, reviewed_body, notes):\n'
                       '    return {"result_json": json.dumps(record_decision(context_json, "' + action + '", reviewer, assessment, reviewed_body, notes), ensure_ascii=False)}\n')
        result = code_node("record_" + action, title, len(nodes), wrapper, variables, {"result_json": "string"})
        result["position"]["y"] = result["positionAbsolute"]["y"] = index * 270 - 100
        result["position"]["x"] = result["positionAbsolute"]["x"] = branch_column * 320
        edges.append(edge(human, result, "__timeout" if action == "timeout" else action))
        nodes.append(result)
    aggregate = analysis.node("review_result", "variable-aggregator", "دریافت نتیجهٔ تصمیم", branch_column + 1, {
        "output_type": "string", "variables": [["record_" + action, "result_json"] for action in
                                               ("approve", "request_changes", "reject", "timeout")]})
    unpack = analysis.node("review_output", "code", "آماده‌سازی نتیجهٔ بررسی", branch_column + 2, {
        "code_language": "python3", "code": "import json\n\ndef main(result_json):\n    return json.loads(result_json)\n",
        "variables": [analysis.selector("result_json", "review_result", "output")],
        "outputs": {name: {"type": "string", "children": None} for name in OUTPUTS}})
    end = analysis.node("end", "end", "ارائهٔ نتیجهٔ بررسی مالک محصول", branch_column + 3, {
        "outputs": [{**analysis.selector(name, "review_output", name), "value_type": "string"} for name in OUTPUTS]})
    for result in nodes[branch_column:]:
        edges.append(edge(result, aggregate))
    edges.extend([edge(aggregate, unpack), edge(unpack, end)])
    nodes.extend([aggregate, unpack, end])
    workflow["workflow"]["graph"] = {"nodes": nodes, "edges": edges, "viewport": {"x": 0, "y": 0, "zoom": 0.5}}
    workflow["app"].update(name="آزمون فرم بررسی کلاسور" if harness else "تحلیل و بررسی درخواست کلاسور",
                           description="تحلیل نیازمندی، توقف برای بررسی مالک محصول و ثبت تصمیم برای متن و نسخهٔ مشخص.")
    return workflow


def manifest(workflow):
    return {"workflow_revision": "0.1", "review_revision": "0.1", "dify_version": "1.17.1",
            "dsl_version": workflow["version"], "analyst_prompt_revision": "0.4",
            "analyst_prompt_sha256": analysis.manifest(analysis.build())["prompt_sha256"],
            "decision_code_sha256": hashlib.sha256((FOLDER / "decision.py").read_bytes()).hexdigest(),
            "workflow_sha256": hashlib.sha256(analysis.dump(workflow).encode()).hexdigest(),
            "default_review_kind": RULES["TRIAL"], "human_input_delivery": "webapp"}


def main():
    parser = argparse.ArgumentParser(description="ساخت فرایند تحلیل و بررسی مالک محصول")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--local", action="store_true")
    parser.add_argument("--harness", action="store_true", help="آزمون فرم با تحلیل ساختگی آماده، بدون فراخوانی مدل")
    args = parser.parse_args()
    workflow = build(args.harness)
    if args.check:
        assert (FOLDER / "workflow.yml").read_text() == analysis.dump(workflow)
        assert json.loads((FOLDER / "manifest.json").read_text()) == manifest(workflow)
        print("فرایند بررسی با دستورالعمل تحلیلگر و قواعد تصمیم مطابق است.")
    elif args.local or args.harness:
        target = ROOT / ".runtime/workflows" / ("klassor-review-harness.local.yml" if args.harness else "klassor-product-review.local.yml")
        subprocess.run(["git", "check-ignore", "-q", str(target)], cwd=ROOT, check=True)
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(target.parent, 0o700)
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as stream:
            stream.write(analysis.dump(workflow))
        print("فایل خصوصی آماده شد:", target)
    else:
        (FOLDER / "workflow.yml").write_text(analysis.dump(workflow))
        (FOLDER / "manifest.json").write_text(json.dumps(manifest(workflow), ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    main()
