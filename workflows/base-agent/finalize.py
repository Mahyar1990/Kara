"""Validate the model contract; execution permissions come only from the platform."""

import hashlib
import json


def main(raw_result, input_json):
    envelope = json.loads(input_json)
    valid = False
    questions = []
    result = "پاسخ مدل با قرارداد خروجی سازگار نبود؛ این اجرا نیازمند بررسی است."
    status = "invalid_output"
    if isinstance(raw_result, str) and 0 < len(raw_result) <= 120000:
        try:
            parsed = json.loads(raw_result)
            if not isinstance(parsed, dict) or set(parsed) != {"status", "result", "questions"}:
                raise ValueError("invalid_contract")
            if parsed["status"] not in ("completed", "needs_input"):
                raise ValueError("invalid_status")
            if not isinstance(parsed["result"], str) or not parsed["result"].strip():
                raise ValueError("empty_result")
            questions = parsed["questions"]
            if not isinstance(questions, list) or len(questions) > 30 or any(
                    not isinstance(q, str) or not q.strip() or len(q) > 2000 for q in questions):
                raise ValueError("invalid_questions")
            if (parsed["status"] == "needs_input") != bool(questions):
                raise ValueError("inconsistent_status")
            status, result, valid = parsed["status"], parsed["result"], True
        except (ValueError, TypeError):
            questions = []
    record = {"template_revision": envelope["template_revision"],
              "project": envelope["project"], "agent_config_id": envelope["agent_config_id"],
              "task_id": envelope["task_id"], "task_revision": envelope["task"]["task_revision"],
              "prepared_at_utc": envelope["prepared_at_utc"], "execution_mode": "trial",
              "output_status": status, "output_contract_valid": valid,
              "human_decision": "unreviewed", "can_execute_tools": False,
              "can_handoff": False, "can_merge": False,
              "result_sha256": hashlib.sha256(result.encode()).hexdigest()}
    report = "# نتیجهٔ آزمایشی ایجنت\n\n" + result
    if questions:
        report += "\n\n## پرسش‌های باقی‌مانده\n\n" + "\n".join("- " + q for q in questions)
    report += "\n\nاین نتیجه برای بررسی انسان است؛ ابزار بیرونی اجرا و تأیید انسانی ثبت نشده است."
    return {"report": report, "result_status": status, "task_id": envelope["task_id"],
            "agent_config_id": envelope["agent_config_id"],
            "questions_json": json.dumps(questions, ensure_ascii=False),
            "run_record_json": json.dumps(record, ensure_ascii=False),
            "quality_note": "ساختار معتبر؛ محتوای نتیجه نیازمند بررسی انسان است" if valid else "قالب پاسخ نامعتبر است"}
