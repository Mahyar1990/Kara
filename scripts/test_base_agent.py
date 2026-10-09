"""Check generic configuration boundaries and output authorization invariants."""
import json
from pathlib import Path
import runpy
import unittest
import yaml
import build_base_agent as builder

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "workflows/base-agent"
prepare = runpy.run_path(str(FOLDER / "prepare.py"))["main"]
finalize = runpy.run_path(str(FOLDER / "finalize.py"))["main"]
BASE = json.loads((ROOT / "fixtures/base-agent/requirement.json").read_text())["inputs"]


class GenericIdentityTests(unittest.TestCase):
    def test_projects_roles_and_task_references_are_not_product_specific(self):
        for filename in ("requirement.json", "editor.json"):
            inputs = json.loads((ROOT / "fixtures/base-agent" / filename).read_text())["inputs"]
            output = prepare(**inputs)
            envelope = json.loads(output["input_json"])
            self.assertEqual(envelope["project"]["name"], inputs["project_name"])
            self.assertEqual(envelope["agent"]["agent_role"], inputs["agent_role"])
            self.assertEqual(envelope["task"]["task_ref"], inputs["task_ref"])
            self.assertFalse(envelope["external_reference_verified"])
            self.assertEqual(envelope["connected_tools"], [])

    def test_configuration_and_task_changes_cannot_reuse_identity(self):
        original = prepare(**BASE)
        self.assertEqual(prepare(**BASE)["task_id"], original["task_id"])
        for key in ("project_name", "agent_role", "agent_goal", "agent_instructions", "output_format"):
            changed = prepare(**{**BASE, key: BASE[key] + " تغییر"})
            self.assertNotEqual(changed["agent_config_id"], original["agent_config_id"])
            self.assertNotEqual(changed["task_id"], original["task_id"])
        for change in ({"task_revision": 2}, {"context_text": "منبع جدید"}, {"task_ref": "OTHER-3"}):
            changed = prepare(**{**BASE, **change})
            self.assertEqual(changed["agent_config_id"], original["agent_config_id"])
            self.assertNotEqual(changed["task_id"], original["task_id"])

    def test_invalid_inputs_stop_before_model(self):
        for change in ({"project_name": " "}, {"task_text": ""}, {"agent_role": None},
                       {"task_revision": True}, {"task_revision": 0}, {"task_revision": 1.5},
                       {"task_revision": float("nan")}, {"context_text": "x" * 10001}):
            with self.subTest(change=list(change)), self.assertRaises(ValueError):
                prepare(**{**BASE, **change})


class TrialOutputTests(unittest.TestCase):
    def setUp(self):
        self.inputs = prepare(**BASE)

    def test_valid_text_never_creates_authority(self):
        output = finalize(json.dumps({"status": "completed", "result": "مدل ادعا می‌کند مرج انجام شده است.",
                                      "questions": []}), self.inputs["input_json"])
        record = json.loads(output["run_record_json"])
        self.assertTrue(record["output_contract_valid"])
        self.assertEqual(record["human_decision"], "unreviewed")
        self.assertEqual(record["execution_mode"], "trial")
        for key in ("can_execute_tools", "can_handoff", "can_merge"):
            self.assertFalse(record[key])
        self.assertEqual(output["task_id"], self.inputs["task_id"])

    def test_invalid_or_forged_outputs_are_not_reported_as_completed(self):
        cases = ["not JSON", "null", json.dumps({"status": "approved", "result": "تأیید", "questions": []}),
                 json.dumps({"status": "completed", "result": "متن", "questions": [], "can_merge": True}),
                 json.dumps({"status": "completed", "result": "متن", "questions": ["سؤال"]}),
                 json.dumps({"status": "needs_input", "result": "متن", "questions": []}),
                 json.dumps({"status": "needs_input", "result": "متن", "questions": [None]}),
                 json.dumps({"status": "completed", "result": " ", "questions": []}), "x" * 120001]
        for raw in cases:
            with self.subTest(raw=raw[:30]):
                output = finalize(raw, self.inputs["input_json"])
                self.assertEqual(output["result_status"], "invalid_output")
                self.assertFalse(json.loads(output["run_record_json"])["output_contract_valid"])

    def test_missing_information_has_questions_and_preserves_review_boundary(self):
        output = finalize(json.dumps({"status": "needs_input", "result": "اطلاعات کافی نیست",
                                      "questions": ["هدف چیست؟"]}), self.inputs["input_json"])
        self.assertEqual(output["result_status"], "needs_input")
        self.assertEqual(json.loads(output["questions_json"]), ["هدف چیست؟"])
        self.assertFalse(json.loads(output["run_record_json"])["can_handoff"])


class TemplateExportTests(unittest.TestCase):
    def test_reproducible_template_has_no_environment_data_or_product_binding(self):
        workflow = builder.build()
        self.assertEqual(yaml.safe_load((FOLDER / "workflow.yml").read_text()), workflow)
        self.assertEqual(json.loads((FOLDER / "manifest.json").read_text()), builder.manifest(workflow))
        exported = builder.dsl.dump(workflow)
        for marker in ("کلاسور", "OVM-", "api_token", "Bearer ", "Cookie:", "/Users/", "sandpod.ir"):
            self.assertNotIn(marker, exported)
        self.assertEqual(workflow["workflow"]["environment_variables"], [])
        agent = next(n["data"] for n in workflow["workflow"]["graph"]["nodes"] if n["id"] == "agent")
        self.assertEqual(agent["model"]["name"], builder.dsl.MODEL_PLACEHOLDER)
        self.assertEqual(agent["prompt_template"][0]["text"], (ROOT / "prompts/base-agent.md").read_text())

    def test_input_references_are_available_at_each_stage(self):
        available = {}
        for node in builder.build()["workflow"]["graph"]["nodes"]:
            data = node["data"]
            fields = data.get("variables", []) + (data.get("outputs", []) if data["type"] == "end" else [])
            for field in fields:
                if "value_selector" in field:
                    source, key = field["value_selector"]
                    self.assertIn(key, available[source])
            if data["type"] == "start":
                available[node["id"]] = {f["variable"] for f in data["variables"]}
            elif data["type"] == "llm":
                self.assertTrue({"agent_config_json", "task_json"}.issubset(available["prepare"]))
                available[node["id"]] = {"text"}
            elif data["type"] == "code":
                available[node["id"]] = set(data.get("outputs", {}))
            else:
                available[node["id"]] = set()


if __name__ == "__main__":
    unittest.main()
