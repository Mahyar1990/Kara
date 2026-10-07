"""Dify output node: keep the human decision outside model-generated text."""

import json
import re


def main(raw_report, input_json):
    if not isinstance(raw_report, str) or not raw_report.strip():
        raise ValueError("متن تحلیل از مدل دریافت نشد.")
    envelope = json.loads(input_json)
    translation = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
    normalized = raw_report.translate(translation)
    decision = re.search(r"(?m)^\s*#{1,6}\s*10(?:[.)،:\-]|\s)", normalized)
    # Digits translate one-to-one, so the match offset still refers to the original.
    body = raw_report[:decision.start()].rstrip() if decision else raw_report.rstrip()
    headings = set(re.findall(r"(?m)^\s*#{1,6}\s*([1-9])(?:[.)،:\-]|\s)", body.translate(translation)))
    missing = [str(index) for index in range(1, 10) if str(index) not in headings]
    quality = "قالب نیازمند بازبینی" if missing else "بخش‌های ۱ تا ۹ حاضرند؛ محتوا نیازمند بررسی انسانی است"
    header = (
        "# پیش‌نویس تحلیل درخواست کلاسور\n\n"
        "- شناسهٔ تحلیل: `" + envelope["analysis_ref"] + "`\n"
        "- نسخهٔ تحلیل: " + str(envelope["analysis_revision"]) + "\n"
        "- وضعیت تصمیم مالک محصول: **بررسی‌نشده**\n"
        "- بررسی قالب: " + quality + "\n\n"
    )
    footer = (
        "\n\n### ۱۰. ثبت تصمیم مالک محصول\n\n"
        "- وضعیت تصمیم: **بررسی‌نشده**\n"
        "- تصمیم‌گیرنده و زمان تصمیم: نامشخص؛ تصمیم انسانی ثبت نشده است.\n"
        "- شناسهٔ تحلیلِ موضوع تصمیم: `" + envelope["analysis_ref"] + "`\n"
        "- دلیل، اصلاح یا پاسخ ثبت‌شده: تصمیم انسانی ثبت نشده است.\n\n"
        "این خروجی برای بررسی مالک محصول است. مجوز تحویل به برنامه‌ریز یا توسعه‌دهنده ایجاد نمی‌کند."
    )
    decision_record = {
        "state": "unreviewed", "analysis_ref": envelope["analysis_ref"],
        "request_fingerprint": envelope["request_fingerprint"],
        "analysis_revision": envelope["analysis_revision"],
        "decided_by": None, "decided_at": None,
        "can_handoff_to_planner": False, "development_ready": False,
    }
    return {
        "report": header + body + footer,
        "analysis_ref": envelope["analysis_ref"],
        "human_decision": "بررسی‌نشده",
        "decision_record_json": json.dumps(decision_record, ensure_ascii=False),
        "quality_note": quality + ("؛ بخش‌های غایب: " + "، ".join(missing) if missing else ""),
    }
