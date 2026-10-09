"""Bind configurable project/agent definitions to one versioned trial task."""

import hashlib
import json
from datetime import datetime, timezone

TEMPLATE_REVISION = "0.1"
LIMITS = {"project_name": 150, "agent_name": 150, "agent_role": 1000,
          "agent_goal": 2000, "agent_instructions": 4000, "output_format": 3000,
          "task_ref": 100, "task_text": 6000, "context_text": 10000}
REQUIRED = {"project_name", "agent_name", "agent_role", "agent_goal", "output_format", "task_text"}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def main(project_name="", agent_name="", agent_role="", agent_goal="", agent_instructions="",
         output_format="", task_ref="", task_text="", context_text="", task_revision=1):
    values = dict(project_name=project_name, agent_name=agent_name, agent_role=agent_role,
                  agent_goal=agent_goal, agent_instructions=agent_instructions,
                  output_format=output_format, task_ref=task_ref, task_text=task_text,
                  context_text=context_text)
    for key, limit in LIMITS.items():
        value = values[key]
        if not isinstance(value, str) or len(value) > limit:
            raise ValueError("نوع یا طول ورودی " + key + " معتبر نیست.")
        if key in REQUIRED and not value.strip():
            raise ValueError("ورودی " + key + " لازم است.")
        values[key] = value.strip()
    if isinstance(task_revision, bool) or not isinstance(task_revision, (int, float)):
        raise ValueError("نسخهٔ کار باید عدد صحیح مثبت باشد.")
    if not 1 <= task_revision <= 1000000 or int(task_revision) != task_revision:
        raise ValueError("نسخهٔ کار باید عدد صحیح مثبت باشد.")
    project = {"name": values["project_name"]}
    agent = {key: values[key] for key in
             ("agent_name", "agent_role", "agent_goal", "agent_instructions", "output_format")}
    agent.update(template_revision=TEMPLATE_REVISION, project=project)
    agent_id = "agent:" + digest(agent)[:20]
    task = {key: values[key] for key in ("task_ref", "task_text", "context_text")}
    task.update(agent_config_id=agent_id, project=project, task_revision=int(task_revision))
    task_id = "task:v" + str(int(task_revision)) + ":" + digest(task)[:20]
    envelope = {"project": project, "agent": agent, "agent_config_id": agent_id,
                "task": task, "task_id": task_id, "template_revision": TEMPLATE_REVISION,
                "prepared_at_utc": datetime.now(timezone.utc).isoformat(),
                "execution_mode": "trial", "connected_tools": [],
                "external_reference_verified": False}
    return {"input_json": json.dumps(envelope, ensure_ascii=False),
            "agent_config_json": json.dumps(agent, ensure_ascii=False),
            "task_json": json.dumps(task, ensure_ascii=False), "task_id": task_id,
            "agent_config_id": agent_id}
