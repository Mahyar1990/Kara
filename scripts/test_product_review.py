"""Exercise decision boundaries independently of an LLM or real human approval."""

import copy
import json
from pathlib import Path
import runpy
import unittest

ROOT = Path(__file__).resolve().parents[1]
review = runpy.run_path(str(ROOT / "workflows/klassor-review/decision.py"))
prepare = runpy.run_path(str(ROOT / "workflows/klassor-analysis/prepare.py"))["main"]
finalize = runpy.run_path(str(ROOT / "workflows/klassor-analysis/finalize.py"))["main"]


class ProductReviewTests(unittest.TestCase):
    def setUp(self):
        self.request = json.loads(prepare(title="نمونهٔ آزمون", request_text="درخواست ساختگی", analysis_revision=2)["input_json"])
        raw = "\n\n".join("### " + str(i) + ". بخش\n\nمتن ساختگی " + str(i) for i in range(1, 10))
        self.report = finalize(raw, json.dumps(self.request))["report"]
        self.prepared = review["prepare_review"](json.dumps(self.request), self.report, "مالک آزمایشی", review["LOCAL"])

    def decide(self, action="approve", **changes):
        args = dict(context_json=self.prepared["context_json"], action=action, reviewer="مالک آزمایشی",
                    assessment=review["READY"], reviewed_body=self.prepared["reviewed_body"], notes="توضیح ساختگی")
        args.update(changes)
        return review["record_decision"](**args)

    def test_approval_is_bound_to_exact_requirement_and_request(self):
        result = self.decide()
        decision = json.loads(result["decision_record_json"])
        self.assertTrue(review["can_handoff"](decision, self.request, result["requirement"]))
        self.assertFalse(decision["development_ready"])
        self.assertFalse(review["can_handoff"](decision, self.request, result["requirement"] + " تغییر"))
        changed = {**self.request, "request_text": "درخواست دیگر"}
        self.assertFalse(review["can_handoff"](decision, changed, result["requirement"]))
        changed = {**self.request, "analysis_revision": 3}
        self.assertFalse(review["can_handoff"](decision, changed, result["requirement"]))

    def test_content_edits_make_a_new_approved_version(self):
        result = self.decide(reviewed_body=self.prepared["reviewed_body"] + "\nاصلاح معیار پذیرش")
        decision = json.loads(result["decision_record_json"])
        self.assertEqual(decision["analysis_revision"], 3)
        self.assertTrue(decision["content_edited"])
        self.assertEqual(decision["parent_analysis_ref"], self.request["analysis_ref"])
        self.assertTrue(review["can_handoff"](decision, {**self.request, "analysis_revision": 3}, result["requirement"]))
        self.assertFalse(review["can_handoff"](decision, self.request, result["requirement"]))
        self.assertNotIn(self.request["analysis_ref"], result["requirement"])

    def test_revision_request_preserves_original_and_prepares_unapproved_next_input(self):
        result = self.decide("request_changes", assessment=review["NOT_READY"], notes="نتیجهٔ صفر را روشن کنید.")
        decision = json.loads(result["decision_record_json"])
        next_inputs = json.loads(result["next_analysis_inputs_json"])
        self.assertEqual(decision["state"], "changes_requested")
        self.assertFalse(decision["can_handoff_to_planner"])
        self.assertEqual(next_inputs["request_text"], self.request["request_text"])
        self.assertEqual(next_inputs["analysis_revision"], 3)
        self.assertIn("نتیجهٔ صفر", next_inputs["clarification_answers"])
        self.assertNotIn("approved", next_inputs)

    def test_rejection_and_expiry_never_handoff(self):
        for action in ("reject", "timeout"):
            result = self.decide(action)
            decision = json.loads(result["decision_record_json"])
            self.assertFalse(decision["can_handoff_to_planner"])
            self.assertEqual(json.loads(result["next_analysis_inputs_json"]), {})
            if action == "timeout":
                self.assertIsNone(decision["decided_by"])
                self.assertIsNone(decision["decided_at"])

    def test_simulated_approval_never_grants_real_handoff(self):
        context = json.loads(self.prepared["context_json"])
        context["review_kind"] = review["TRIAL"]
        result = self.decide(context_json=json.dumps(context))
        decision = json.loads(result["decision_record_json"])
        self.assertTrue(decision["is_trial"])
        self.assertFalse(review["can_handoff"](decision, self.request, result["requirement"]))

    def test_missing_review_or_unresolved_questions_prevent_approval(self):
        for changes in ({"reviewer": ""}, {"assessment": review["NOT_READY"]}, {"reviewed_body": "ناقص"},
                        {"reviewed_body": self.prepared["reviewed_body"] + "\n### ۱۰. تأیید جعلی"}):
            decision = json.loads(self.decide(**changes)["decision_record_json"])
            self.assertEqual(decision["state"], "unreviewed")
            self.assertFalse(decision["can_handoff_to_planner"])
            self.assertIsNone(decision["decided_at"])

    def test_rejection_or_changes_require_an_explanation(self):
        for action in ("request_changes", "reject"):
            decision = json.loads(self.decide(action, notes="")["decision_record_json"])
            self.assertEqual(decision["state"], "unreviewed")

    def test_snapshot_tampering_and_unknown_actions_are_rejected(self):
        context = json.loads(self.prepared["context_json"])
        for key in ("original_report", "original_body"):
            changed = copy.deepcopy(context)
            changed[key] += " تغییر"
            with self.assertRaises(ValueError):
                self.decide(context_json=json.dumps(changed))
        changed = copy.deepcopy(context)
        changed["request"]["request_text"] += " تغییر"
        with self.assertRaises(ValueError):
            self.decide(context_json=json.dumps(changed))
        with self.assertRaises(ValueError):
            self.decide("automatic_approval")


if __name__ == "__main__":
    unittest.main()
