"""Dify preparation node: preserve the manual request and identify its version."""

import hashlib
import json
import re
from datetime import datetime, timezone


def main(jira_key="", title="", request_text="", sources_text="", clarification_answers="", analysis_revision=1):
    values = (jira_key, title, request_text, sources_text, clarification_answers)
    if not all(isinstance(value, str) for value in values):
        raise ValueError("ورودی‌های متنی باید متن باشند.")
    if not title.strip() or not request_text.strip():
        raise ValueError("عنوان و متن اصلی درخواست لازم است.")
    if any(len(value) > limit for value, limit in zip(values, (40, 200, 6000, 8000, 4000))):
        raise ValueError("طول یکی از ورودی‌ها بیشتر از حد فرم است.")
    jira_key = jira_key.strip()
    if jira_key and not re.fullmatch(r"OVM-[0-9]+", jira_key):
        raise ValueError("شناسهٔ جیرا باید مانند OVM-1332 باشد یا خالی بماند.")
    if isinstance(analysis_revision, bool) or not isinstance(analysis_revision, (int, float)):
        raise ValueError("شمارهٔ نسخه باید عدد صحیح مثبت باشد.")
    if not 1 <= analysis_revision <= 1000000 or int(analysis_revision) != analysis_revision:
        raise ValueError("شمارهٔ نسخه باید عدد صحیح مثبت باشد.")
    snapshot = {
        "product": "کلاسور", "jira_key": jira_key, "title": title,
        "request_text": request_text, "sources_text": sources_text,
        "clarification_answers": clarification_answers,
    }
    canonical = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    revision = int(analysis_revision)
    analysis_ref = (jira_key or "draft") + ":v" + str(revision) + ":" + fingerprint[:16]
    envelope = {
        **snapshot, "analysis_revision": revision, "analysis_ref": analysis_ref,
        "request_fingerprint": fingerprint,
        "prepared_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_method": "ورود دستی؛ وجود درخواست در جیرا بررسی نشده است",
        "prompt_revision": "0.4",
    }
    return {"input_json": json.dumps(envelope, ensure_ascii=False), "analysis_ref": analysis_ref}
