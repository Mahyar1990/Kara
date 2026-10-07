"""Version-bound local product review; decisions originate in a Dify human form."""

import hashlib
import json
import re
from datetime import datetime, timezone


READY = "معیارهای پذیرش بررسی شده‌اند و ابهام محصولی باقی نمانده"
NOT_READY = "نیاز به اصلاح یا روشن‌سازی باقی است"
TRIAL = "نمونهٔ آزمایشی"
LOCAL = "درخواست محلی"
FIELDS = ("product", "jira_key", "title", "request_text", "sources_text", "clarification_answers")
DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def reference(request, revision):
    snapshot = {name: request[name] for name in FIELDS}
    fingerprint = digest(json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return (request["jira_key"] or "draft") + ":v" + str(revision) + ":" + fingerprint[:16], fingerprint


def sections(text):
    return set(re.findall(r"(?m)^\s*#{1,6}\s*([2-9])(?:[.)،:\-]|\s)", text.translate(DIGITS)))


def prepare_review(input_json, report, reviewer_name, review_kind):
    request = json.loads(input_json)
    if not isinstance(request, dict) or any(not isinstance(request.get(name), str) for name in FIELDS):
        raise ValueError("اطلاعات درخواست کامل نیست.")
    if request["product"] != "کلاسور" or not isinstance(request.get("prepared_at_utc"), str):
        raise ValueError("محصول یا زمان تهیهٔ تحلیل معتبر نیست.")
    revision = request.get("analysis_revision")
    if type(revision) is not int or not 1 <= revision < 1000000:
        raise ValueError("نسخهٔ تحلیل معتبر نیست.")
    analysis_ref, fingerprint = reference(request, revision)
    if request.get("analysis_ref") != analysis_ref or request.get("request_fingerprint") != fingerprint:
        raise ValueError("شناسه و متن درخواست به یک نسخه تعلق ندارند.")
    if not isinstance(report, str) or not report.strip() or len(report) > 120000:
        raise ValueError("متن تحلیل معتبر نیست.")
    if review_kind not in (TRIAL, LOCAL):
        raise ValueError("نوع درخواست معتبر نیست.")
    if not isinstance(reviewer_name, str) or not 1 <= len(reviewer_name.strip()) <= 100:
        raise ValueError("نام مالک محصول لازم است.")
    normalized = report.translate(DIGITS)
    start = re.search(r"(?m)^\s*#{1,6}\s*2(?:[.)،:\-]|\s)", normalized)
    end = re.search(r"(?m)^\s*#{1,6}\s*10(?:[.)،:\-]|\s)", normalized)
    if not start or not end or start.start() >= end.start():
        raise ValueError("بخش‌های تحلیل برای بررسی کامل نیستند.")
    body = report[start.start():end.start()].strip()
    context = {"request": request, "original_report": report, "original_body": body,
               "original_report_sha256": digest(report), "reviewer_name": reviewer_name.strip(),
               "review_kind": review_kind, "review_revision": "0.1"}
    return {"context_json": json.dumps(context, ensure_ascii=False), "reviewed_body": body,
            "original_report": report,
            "request_display": "\n\n".join([
                "**نوع درخواست:** " + review_kind,
                "**عنوان:** " + request["title"],
                "**متن اصلی درخواست**\n\n" + request["request_text"],
                "**منابع موجود**\n\n" + (request["sources_text"] or "منبعی ارائه نشده است."),
                "**پاسخ‌های قبلی**\n\n" + (request["clarification_answers"] or "پاسخی ثبت نشده است."),
            ]), "reviewer_options": [reviewer_name.strip()], "analysis_ref": analysis_ref}


def record_decision(context_json, action, reviewer="", assessment="", reviewed_body="", notes=""):
    context = json.loads(context_json)
    request = context["request"]
    # Validate the saved snapshot again rather than trusting a model-generated decision.
    validated = prepare_review(json.dumps(request), context["original_report"], context["reviewer_name"], context["review_kind"])
    if (context["original_report_sha256"] != digest(context["original_report"])
            or context["original_body"] != validated["reviewed_body"]):
        raise ValueError("متن تحلیل پس از آماده‌سازی تغییر کرده است.")
    if action not in ("approve", "request_changes", "reject", "timeout"):
        raise ValueError("تصمیم انتخاب‌شده معتبر نیست.")
    if not all(isinstance(value, str) for value in (reviewer, assessment, reviewed_body, notes)):
        raise ValueError("اطلاعات فرم باید متن باشد.")
    body = reviewed_body.strip()
    error = ""
    if action != "timeout":
        if reviewer != context["reviewer_name"]:
            error = "نام تصمیم‌گیرنده با فرم بررسی تطبیق ندارد."
        elif assessment not in (READY, NOT_READY):
            error = "نتیجهٔ بررسی معیارها انتخاب نشده است."
        elif len(notes) > 4000 or len(body) > 120000:
            error = "متن فرم از حد مجاز بیشتر است."
        elif action == "approve" and (assessment != READY or sections(body) != set("23456789")
                or re.search(r"(?m)^\s*#{1,6}\s*(?:1|10)(?:[.)،:\-]|\s)", body.translate(DIGITS))):
            error = "تأیید ثبت نشد؛ ابهام‌ها و بخش‌های معیارهای نیازمندی باید کامل بررسی شوند."
        elif action in ("request_changes", "reject") and not notes.strip():
            error = "برای درخواست اصلاح یا رد، توضیح لازم است."
    states = {"approve": "approved", "request_changes": "changes_requested", "reject": "rejected", "timeout": "expired"}
    state = "unreviewed" if error else states[action]
    edited = state == "approved" and body != context["original_body"]
    revision = request["analysis_revision"] + int(edited)
    analysis_ref, fingerprint = reference(request, revision)
    labels = {"approved": "تأیید", "changes_requested": "درخواست اصلاح", "rejected": "رد",
              "expired": "مهلت بررسی پایان یافته", "unreviewed": "بررسی‌نشده"}
    timestamp = datetime.now(timezone.utc).isoformat() if action != "timeout" and not error else None
    selected_body = body if state == "approved" else context["original_body"]
    requirement = (
        "### ۱. مشخصات تحلیل\n\n"
        "- شناسهٔ درخواست: " + (request["jira_key"] or "نامشخص؛ پیش‌نویس محلی") + "\n"
        "- شناسهٔ تحلیل: `" + analysis_ref + "`\n"
        "- محصول: " + request["product"] + "\n"
        "- عنوان اصلی درخواست: " + request["title"] + "\n"
        "- نسخهٔ تحلیل: " + str(revision) + "\n"
        "- زمان تهیهٔ پیش‌نویس: " + request["prepared_at_utc"] + "\n"
        "- وضعیت بررسی معیارها: " + (assessment if action != "timeout" else "تصمیمی دریافت نشد") + "\n\n" + selected_body
    )
    decision = {
        "schema_version": "1", "state": state, "analysis_ref": analysis_ref,
        "analysis_revision": revision, "request_fingerprint": fingerprint,
        "requirement_sha256": digest(requirement), "parent_analysis_ref": request["analysis_ref"],
        "parent_report_sha256": context["original_report_sha256"], "content_edited": edited,
        "decided_by": reviewer if timestamp else None, "decided_at": timestamp,
        "notes": notes, "assessment": assessment, "selected_action": action,
        "decision_source": "dify_human_input", "identity_source": "local_form_selection",
        "is_trial": context["review_kind"] == TRIAL,
        "can_handoff_to_planner": state == "approved" and context["review_kind"] == LOCAL,
        "development_ready": False,
    }
    decision["decision_id"] = digest(json.dumps(decision, ensure_ascii=False, sort_keys=True))[:24]
    next_inputs = {}
    if state == "changes_requested":
        next_inputs = {name: request[name] for name in FIELDS if name != "product"}
        next_inputs["analysis_revision"] = request["analysis_revision"] + 1
        next_inputs["clarification_answers"] = "\n\n".join(filter(None, [request["clarification_answers"],
            "پاسخ یا اصلاح مالک محصول برای " + request["analysis_ref"] + ":\n" + notes]))
        next_inputs["reviewer_name"] = reviewer
        next_inputs["review_kind"] = context["review_kind"]
    guidance = {
        "approved": "این نسخه تأیید شد؛ برنامه‌ریزی فنی مرحلهٔ بعد است.",
        "changes_requested": "درخواست اصلاح ثبت شد. ورودی بازتحلیل، پاسخ مالک محصول و شمارهٔ نسخهٔ بعدی را دارد؛ تحلیل دوباره باید جداگانه اجرا و بررسی شود.",
        "rejected": "این پیشنهاد رد شد و به برنامه‌ریزی تحویل نمی‌شود.",
        "expired": "تصمیمی دریافت نشد؛ بررسی تازه لازم است.",
        "unreviewed": error,
    }[state]
    if decision["is_trial"]:
        guidance += " این یک نمونهٔ آزمایشی است و مجوز واقعی تحویل ایجاد نمی‌کند."
    if next_inputs and len(next_inputs["clarification_answers"]) > 4000:
        guidance += " متن پاسخ‌ها از حد فرم تحلیل بیشتر است؛ پیش از بازتحلیل، آن را با حفظ معنا کوتاه کنید."
    footer = ("\n\n### ۱۰. ثبت تصمیم مالک محصول\n\n- وضعیت تصمیم: **" + labels[state] + "**\n"
              "- تصمیم‌گیرنده: " + (decision["decided_by"] or "ثبت نشده") + "\n"
              "- زمان تصمیم: " + (timestamp or "ثبت نشده") + "\n"
              "- شناسهٔ تصمیم: `" + decision["decision_id"] + "`\n"
              "- شناسهٔ تحلیلِ موضوع تصمیم: `" + analysis_ref + "`\n"
              "- توضیح: " + (notes or "توضیحی وارد نشده است.") + "\n\n" + guidance)
    return {"report": requirement + footer, "requirement": requirement, "analysis_ref": analysis_ref,
            "human_decision": labels[state], "decision_record_json": json.dumps(decision, ensure_ascii=False),
            "next_analysis_inputs_json": json.dumps(next_inputs, ensure_ascii=False),
            "revision_proposal": body if state == "changes_requested" and body != context["original_body"] else "",
            "next_step": guidance}


def can_handoff(decision, request, requirement):
    analysis_ref, fingerprint = reference(request, request["analysis_revision"])
    return (decision.get("state") == "approved" and decision.get("is_trial") is False
            and decision.get("decision_source") == "dify_human_input"
            and decision.get("can_handoff_to_planner") is True
            and decision.get("analysis_ref") == analysis_ref
            and decision.get("analysis_revision") == request["analysis_revision"]
            and decision.get("request_fingerprint") == fingerprint
            and decision.get("requirement_sha256") == digest(requirement)
            and bool(decision.get("decided_by")) and bool(decision.get("decided_at")))
