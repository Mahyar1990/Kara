"""Planning boundaries. Embedded after the canonical product-review rules.

Decision arguments must come from native human-input nodes in this workflow,
never a user/model-supplied decision JSON. This is not organization SSO.
"""

import hashlib
import json
import re
from datetime import datetime, timezone

SOURCE_READY = "منابع همین نسخه را بررسی کرده‌ام و برای استفاده در مدل مناسب‌اند"
SOURCE_NOT_READY = "منابع هنوز بررسی نشده‌اند یا به اصلاح نیاز دارند"
PLANNING_STATES = {
    "needs_product_decision": "نیازمند تصمیم محصول",
    "needs_technical_review": "نیازمند بررسی فنی",
    "ready_for_technical_discussion": "آمادهٔ گفت‌وگوی فنی",
}


def canonical_hash(value):
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode()).hexdigest()


def stopped(reason, state="در انتظار تأیید نیازمندی"):
    result = {"planning_status": state, "planning_report": reason, "planning_record_json": "{}",
              "planning_notice": "برنامه‌ریز اجرا نشد. توسعه و مرج فعال نشده‌اند.",
              "development_ready": "false", "can_merge": "false"}
    return {"can_run": 0, "gate_context_json": "{}", "planner_input_json": "{}",
            "repository_rules_json": "{}", "technical_context_json": "{}",
            "blocked_result_json": json.dumps(result, ensure_ascii=False)}


def prepare_planning(input_json, review_result_json, agent_context_json, allow_trial=False):
    try:
        request = json.loads(input_json)
        result = json.loads(review_result_json)
        decision = json.loads(result["decision_record_json"])
        requirement = result["requirement"]
        original_ref, original_fingerprint = reference(request, request["analysis_revision"])
        if request["analysis_ref"] != original_ref or request["request_fingerprint"] != original_fingerprint:
            return stopped("متن و نسخهٔ درخواست اولیه تطبیق ندارند.")
        if decision["state"] != "approved":
            state = "متوقف طبق تصمیم مالک محصول" if decision["state"] in ("rejected", "changes_requested") else "در انتظار تأیید نیازمندی"
            return stopped("تأیید معتبر نیازمندی برای برنامه‌ریزی دریافت نشده است.", state)
        stored_id = decision["decision_id"]
        values = {key: value for key, value in decision.items() if key != "decision_id"}
        expected_id = hashlib.sha256(json.dumps(values, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:24]
        if stored_id != expected_id:
            return stopped("رکورد تصمیم پس از ثبت تغییر کرده است.")
        revision = decision["analysis_revision"]
        if type(revision) is not int or type(decision["content_edited"]) is not bool or revision != request["analysis_revision"] + int(decision["content_edited"]):
            return stopped("نسخهٔ تصمیم با نسخهٔ نیازمندی بررسی‌شده مطابق نیست.")
        approved_request = {**request, "analysis_revision": revision}
        approved_ref, fingerprint = reference(approved_request, revision)
        decided_at = datetime.fromisoformat(decision["decided_at"])
        if (decision["analysis_ref"] != approved_ref or result["analysis_ref"] != approved_ref
                or decision["parent_analysis_ref"] != original_ref
                or decision["request_fingerprint"] != fingerprint
                or decision["requirement_sha256"] != digest(requirement)
                or decision["decision_source"] != "dify_human_input"
                or decision["identity_source"] != "local_form_selection"
                or decision["selected_action"] != "approve" or decision["assessment"] != READY
                or not isinstance(decision["decided_by"], str) or not decision["decided_by"].strip()
                or decided_at.tzinfo is None or len(requirement) > 120000):
            return stopped("تصمیم، متن، هویت انتخاب‌شده یا زمان ثبت برای تحویل قابل تطبیق نیست.")
        if decision["is_trial"] is True:
            if not allow_trial or decision["can_handoff_to_planner"] is not False:
                return stopped("تصمیم آزمایشی اجازهٔ تحویل واقعی نمی‌دهد.")
        elif decision["is_trial"] is not False or not can_handoff(decision, approved_request, requirement):
            return stopped("مجوز برنامه‌ریزی از مسیر بررسی انسانی معتبر دریافت نشده است.")
        context = json.loads(agent_context_json)
        payload = {key: value for key, value in context.items() if key != "agent_context_id"}
        if context.get("product_id") != "klassor" or context["agent_context_id"] != "agent-context:" + canonical_hash(payload):
            return stopped("بستهٔ زمینهٔ محصول موجود نیست یا با نسخهٔ ثبت‌شده مطابقت ندارد.", "نیازمند بررسی فنی")
        if (result.get("source_review") != SOURCE_READY
                or result.get("reviewed_agent_context_id") != context["agent_context_id"]):
            return stopped("منابع همین نسخه هنوز برای استفاده در مدل بررسی نشده‌اند.", "نیازمند بررسی فنی")
        if not context.get("repository_policies") or not context.get("project_navigation"):
            return stopped("قواعد مخزن و نقشهٔ پروژه در بسته موجود نیستند.", "نیازمند بررسی فنی")
        loaded = context["repository_policies"] + context.get("selected_repository_workflows", []) + context.get("documentation_indexes", []) + context.get("selected_documentation", [])
        source_ids = [source["id"] for source in loaded] + [item["source"]["id"] for item in context["project_navigation"]]
        for source in loaded:
            if hashlib.sha256(source["content"].encode()).hexdigest() != source["content_sha256"]:
                return stopped("محتوای یکی از منابع با هش آن تطبیق ندارد.", "نیازمند بررسی فنی")
        gate = {"analysis_ref": approved_ref, "decision_id": stored_id,
                "requirement_sha256": decision["requirement_sha256"], "agent_context_id": context["agent_context_id"],
                "knowledge_id": context["knowledge_id"], "technical_context_id": context["technical_context_id"],
                "repository_snapshots": context["repository_snapshots"], "loaded_source_ids": sorted(set(source_ids)),
                "is_trial": decision["is_trial"], "development_ready": False, "can_merge": False}
        technical = {key: value for key, value in context.items() if key not in ("repository_policies", "selected_repository_workflows")}
        rules = {"repository_policies": context["repository_policies"], "selected_repository_workflows": context.get("selected_repository_workflows", [])}
        return {"can_run": 1, "gate_context_json": json.dumps(gate, ensure_ascii=False),
                "planner_input_json": json.dumps({"requirement": requirement, "decision": decision, "is_trial": decision["is_trial"]}, ensure_ascii=False),
                "repository_rules_json": json.dumps(rules, ensure_ascii=False),
                "technical_context_json": json.dumps(technical, ensure_ascii=False), "blocked_result_json": "{}"}
    except (KeyError, TypeError, ValueError, AttributeError):
        return stopped("اطلاعات لازم برای تطبیق تصمیم و منابع کامل یا معتبر نیست.")


def finalize_planning(raw_plan, gate_context_json):
    gate = json.loads(gate_context_json)
    errors = []
    try:
        plan = json.loads(raw_plan.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip())
        report = plan["report"]
        state = plan["status"]
        source_ids = plan["source_ids"]
        if state not in PLANNING_STATES or not isinstance(report, str) or not report.strip() or len(report) > 120000:
            raise ValueError("نامعتبر")
        parts = set(re.findall(r"(?m)^\s*#{1,6}\s*([1-8])(?:[.)،:\-]|\s)", report.translate(DIGITS)))
        if parts != set("12345678"):
            errors.append("همهٔ هشت بخش بستهٔ توسعه در خروجی دیده نشدند.")
        if not isinstance(source_ids, list) or not all(isinstance(value, str) for value in source_ids):
            raise ValueError("منبع نامعتبر")
        if set(source_ids) - set(gate["loaded_source_ids"]):
            errors.append("خروجی به منبعی استناد کرده که متنش در این اجرا دریافت نشده است.")
        if not source_ids:
            errors.append("خروجی منبع دریافت‌شده‌ای را برای پیشنهاد فنی ثبت نکرده است.")
    except (ValueError, KeyError, TypeError, AttributeError):
        report = raw_plan[:120000] if isinstance(raw_plan, str) else "خروجی برنامه‌ریز قابل خواندن نیست."
        state, source_ids = "needs_technical_review", []
        errors.append("قالب ساختاری خروجی معتبر نیست؛ متن فقط برای بررسی نگهداری شد.")
    if errors:
        state = "needs_technical_review"
    record = {**gate, "planning_status": state, "source_ids": source_ids, "quality_issues": errors,
              "report_sha256": digest(report), "prepared_at": datetime.now(timezone.utc).isoformat(),
              "technical_discussion_recorded": False, "development_ready": False, "can_merge": False}
    record["planning_id"] = "plan:" + canonical_hash(record)
    notice = "این خروجی پیش‌نویس است؛ بررسی مالک محصول و گفت‌وگو با TL و توسعه‌دهنده هنوز ثبت نشده‌اند. توسعه و مرج فعال نشده‌اند."
    if gate["is_trial"]:
        notice = "نمونهٔ ساختگی و اجرای آزمایشی؛ هیچ تأیید واقعی یا مجوز توسعه و مرج ایجاد نشده است. " + notice
    if errors:
        notice += " " + " ".join(errors)
    return {"planning_status": PLANNING_STATES[state], "planning_report": report,
            "planning_record_json": json.dumps(record, ensure_ascii=False), "planning_notice": notice,
            "development_ready": "false", "can_merge": "false"}
