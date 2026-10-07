import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from wfmcp import spec
from wfmcp.engine import Engine, EngineError
from wfmcp.store import Store
from wfmcp.teams import ConsoleNotifier

ROOT = Path(__file__).resolve().parent.parent
DATA_FIX = (ROOT / "workflows" / "data_fix_approval.yaml").read_text()
ONBOARDING = (ROOT / "workflows" / "mandate_onboarding_lite.yaml").read_text()

INPUTS = {
    "record_id": "0015g00000ABC",
    "record_url": "https://example.my.salesforce.com/0015g00000ABC",
    "owner_email": "owner@example.com",
    "issue": "Country is blank",
}


class FakeClock:
    def __init__(self):
        self.t = datetime(2026, 10, 7, 9, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.t

    def advance(self, **kw):
        self.t += timedelta(**kw)


def make_engine():
    clock = FakeClock()
    notes = ConsoleNotifier()
    eng = Engine(Store(":memory:"), notes, callback_base="https://wf.example.com", secret="test-secret", now=clock)
    eng.register_type(DATA_FIX)
    eng.register_type(ONBOARDING)
    return eng, notes, clock


class SpecTests(unittest.TestCase):
    def test_examples_parse(self):
        self.assertEqual(spec.parse(DATA_FIX).order, ["propose", "approve", "apply", "done"])
        self.assertEqual(len(spec.parse(ONBOARDING).steps), 8)

    def test_reports_all_problems(self):
        bad = """
name: broken
version: 1
steps:
  - {id: a, kind: agent, needs: [b]}
  - {id: b, kind: approval, title: x, needs: [a], on_timeout: escalate}
  - {id: c, kind: notify, body: hi, when: {step: zzz, eq: 1}}
"""
        with self.assertRaises(spec.SpecError) as cm:
            spec.parse(bad)
        msg = str(cm.exception)
        for frag in ("requires 'instructions'", "dependency cycle", "unknown step 'zzz'", "no escalate_to", "on_timeout but no timeout", "needs 'output'"):
            self.assertIn(frag, msg)

    def test_schema_rejects_unknown_keys(self):
        with self.assertRaises(spec.SpecError):
            spec.parse("name: x\nversion: 1\nsteps: [{id: a, kind: agent, instructions: hi, colour: red}]")


class RunTests(unittest.TestCase):
    def test_happy_path_with_approval(self):
        eng, notes, clock = make_engine()
        run = eng.start("data_fix_approval", INPUTS, requested_by="agent:cowork")
        self.assertEqual(run["status"], "running")
        self.assertEqual([w["step_id"] for w in run["work_items"]], ["propose"])
        self.assertEqual(notes.sent[0]["target"], {"channel": "agent-audit"})  # audit on start

        work = eng.claim(run["id"], "propose", worker="cowork:alice")
        self.assertIn("0015g00000ABC", work["instructions"])
        self.assertEqual(work["expected_outputs"], ["summary", "changes", "confidence"])
        with self.assertRaises(EngineError):
            eng.claim(run["id"], "propose", worker="someone-else")
        with self.assertRaises(EngineError):  # missing outputs
            eng.complete(run["id"], "propose", {"summary": "x"})

        run = eng.complete(run["id"], "propose", {"summary": "Set country to CH.", "changes": {"Country": "CH"}, "confidence": 0.7}, worker="cowork:alice")
        self.assertEqual(run["steps"]["approve"]["status"], "waiting")
        self.assertEqual(run["waiting_on"][0]["assigned_to"], "owner@example.com")
        card = notes.sent[-1]
        self.assertEqual(card["target"], {"user": "owner@example.com"})
        titles = [a["title"] for a in card["card"]["actions"]]
        self.assertEqual(titles, ["Approved", "Rejected", "Open record"])
        self.assertIn("Set country to CH.", card["card"]["body"][1]["text"])
        self.assertIn('{"Country": "CH"}', card["card"]["body"][1]["text"])

        # click the Approve button: verify token then decide
        url = card["card"]["actions"][0]["url"]
        token = url.rsplit("/decide/", 1)[1]
        rid, sid, choice = eng.verify_token(token)
        run = eng.decide(rid, sid, choice, decided_by="owner@example.com")
        self.assertEqual(run["steps"]["apply"]["status"], "ready")
        with self.assertRaises(EngineError):  # cannot decide twice
            eng.decide(rid, sid, choice)

        eng.claim(run["id"], "apply", "cowork:alice")
        run = eng.complete(run["id"], "apply", {"applied": True, "details": "ok"})
        self.assertEqual(run["status"], "completed")
        self.assertEqual(run["steps"]["done"]["status"], "completed")
        done_card = notes.sent[-2]  # last is the audit "completed" card
        self.assertEqual(done_card["target"], {"channel": "sales-ops"})
        self.assertIn("Decision: approved. Applied: True.", done_card["card"]["body"][1]["text"])
        kinds = [e["kind"] for e in eng.store.events(run["id"])]
        self.assertEqual(kinds[0], "run.started")
        self.assertEqual(kinds[-1], "run.completed")

    def test_high_confidence_skips_approval(self):
        eng, notes, clock = make_engine()
        run = eng.start("data_fix_approval", INPUTS)
        eng.claim(run["id"], "propose", "w")
        run = eng.complete(run["id"], "propose", {"summary": "s", "changes": {}, "confidence": 0.99})
        self.assertEqual(run["steps"]["approve"]["status"], "skipped")
        self.assertEqual(run["steps"]["apply"]["status"], "ready")

    def test_rejection_skips_apply_and_completes(self):
        eng, notes, clock = make_engine()
        run = eng.start("data_fix_approval", INPUTS)
        eng.claim(run["id"], "propose", "w")
        eng.complete(run["id"], "propose", {"summary": "s", "changes": {}, "confidence": 0.1})
        run = eng.decide(run["id"], "approve", "rejected", decided_by="owner@example.com", comment="wrong")
        self.assertEqual(run["steps"]["apply"]["status"], "skipped")
        # a skipped dependency still satisfies `needs`, so the closing notification goes out
        self.assertEqual(run["steps"]["done"]["status"], "completed")
        self.assertIn("Decision: rejected.", notes.sent[-2]["card"]["body"][1]["text"])
        self.assertEqual(run["status"], "completed")

    def test_reminder_then_timeout_rejects(self):
        eng, notes, clock = make_engine()
        run = eng.start("data_fix_approval", INPUTS)
        eng.claim(run["id"], "propose", "w")
        eng.complete(run["id"], "propose", {"summary": "s", "changes": {}, "confidence": 0.1})
        self.assertEqual(eng.tick(), [])
        clock.advance(hours=5)
        self.assertEqual(eng.tick(), [{"run": run["id"], "step": "approve", "action": "reminded"}])
        self.assertTrue(notes.sent[-1]["card"]["body"][0]["text"].startswith("Reminder:"))
        self.assertEqual(eng.tick(), [])  # reminded once only
        clock.advance(hours=20)
        self.assertEqual(eng.tick(), [{"run": run["id"], "step": "approve", "action": "auto-rejected"}])
        run = eng.get_run(run["id"])
        self.assertEqual(run["steps"]["approve"]["outputs"]["decision"], "rejected")
        self.assertEqual(run["status"], "completed")

    def test_escalation_reassigns_once_then_fails(self):
        eng, notes, clock = make_engine()
        run = eng.start("mandate_onboarding_lite", {
            "mandate_name": "Pension X", "opportunity_id": "006", "ima_document_url": "https://sp/ima.docx",
            "onboarding_lead": "lead@example.com", "compliance_reviewer": "comp@example.com"})
        eng.claim(run["id"], "extract_terms", "w")
        run = eng.complete(run["id"], "extract_terms", {"terms": {"guidelines": ["no tobacco"]}, "deviations": [], "low_confidence_fields": ["fees"]})
        self.assertEqual(run["steps"]["review_terms"]["assigned_to"], "lead@example.com")
        clock.advance(days=2, minutes=1)
        acts = eng.tick()
        self.assertIn({"run": run["id"], "step": "review_terms", "action": "escalated", "to": "onboarding-leads@example.com"}, acts)
        self.assertEqual(notes.sent[-1]["target"], {"user": "onboarding-leads@example.com"})
        self.assertTrue(notes.sent[-1]["card"]["body"][0]["text"].startswith("Escalated:"))
        clock.advance(days=2, minutes=1)
        acts = eng.tick()
        self.assertIn({"run": run["id"], "step": "review_terms", "action": "failed"}, acts)
        self.assertEqual(eng.get_run(run["id"])["status"], "failed")

    def test_parallel_fanout_and_custom_options(self):
        eng, notes, clock = make_engine()
        run = eng.start("mandate_onboarding_lite", {
            "mandate_name": "Pension X", "opportunity_id": "006", "ima_document_url": "https://sp/ima.docx",
            "onboarding_lead": "lead@example.com", "compliance_reviewer": "comp@example.com"})
        eng.claim(run["id"], "extract_terms", "w")
        eng.complete(run["id"], "extract_terms", {"terms": {"guidelines": []}, "deviations": [], "low_confidence_fields": []})
        run = eng.decide(run["id"], "review_terms", "done", "lead@example.com")
        # review done unlocks two agent steps in parallel
        self.assertEqual(sorted(w["step_id"] for w in run["work_items"]), ["code_guidelines", "setup_systems"])
        self.assertEqual(len(eng.next_work()), 2)
        eng.claim(run["id"], "setup_systems", "w1")
        eng.complete(run["id"], "setup_systems", {"setup": {}, "blockers": []})
        eng.claim(run["id"], "code_guidelines", "w2")
        run = eng.complete(run["id"], "code_guidelines", {"rules": [], "tests": [], "open_questions": []})
        self.assertEqual(run["steps"]["readiness"]["status"], "pending")  # waits on approval
        run = eng.decide(run["id"], "approve_guidelines", "approved", "comp@example.com")
        self.assertEqual(run["steps"]["readiness"]["status"], "ready")
        eng.claim(run["id"], "readiness", "w")
        run = eng.complete(run["id"], "readiness", {"ready": True, "report": "all green"})
        self.assertEqual([a["title"] for a in notes.sent[-1]["card"]["actions"]], ["Go", "No_go"])
        with self.assertRaises(EngineError):
            eng.decide(run["id"], "go_live", "approved")
        run = eng.decide(run["id"], "go_live", "go", "lead@example.com")
        self.assertEqual(run["status"], "completed")
        self.assertIn("lead@example.com", notes.sent[-2]["card"]["body"][1]["text"])

    def test_inputs_are_validated(self):
        eng, _, _ = make_engine()
        with self.assertRaises(EngineError) as cm:
            eng.start("data_fix_approval", {"record_id": "x"})
        self.assertIn("required property", str(cm.exception))

    def test_token_tamper_and_expiry(self):
        eng, _, clock = make_engine()
        tok = eng.decision_token("r", "s", "approved")
        self.assertEqual(eng.verify_token(tok), ("r", "s", "approved"))
        with self.assertRaises(EngineError):
            eng.verify_token(tok.replace("approved", "rejected"))
        clock.advance(days=15)
        with self.assertRaises(EngineError):
            eng.verify_token(tok)

    def test_auto_step_and_cancel(self):
        eng, notes, clock = make_engine()
        eng.register_type("""
name: auto_demo
version: 1
steps:
  - id: compute
    kind: auto
    action: {type: set, values: {total: 42, who: "{{ inputs.name }}"}}
  - id: wait
    kind: human
    needs: [compute]
    title: Check total {{ steps.compute.outputs.total }} for {{ steps.compute.outputs.who }}
    channel: sales-ops
""")
        run = eng.start("auto_demo", {"name": "Bob"})
        self.assertEqual(run["steps"]["compute"]["outputs"], {"total": 42, "who": "Bob"})
        self.assertEqual(notes.sent[-1]["card"]["body"][0]["text"], "Check total 42 for Bob")
        run = eng.cancel(run["id"], "no longer needed")
        self.assertEqual(run["status"], "cancelled")
        self.assertEqual(run["steps"]["wait"]["status"], "skipped")

    def test_persistence_survives_restart(self):
        db = Store(":memory:")
        clock = FakeClock()
        eng = Engine(db, ConsoleNotifier(), secret="s", now=clock)
        eng.register_type(DATA_FIX)
        run = eng.start("data_fix_approval", INPUTS)
        eng2 = Engine(db, ConsoleNotifier(), secret="s", now=clock)  # fresh engine, same store
        self.assertEqual([t["name"] for t in eng2.types()], ["data_fix_approval"])
        self.assertEqual(eng2.get_run(run["id"])["status"], "running")
        self.assertEqual(len(eng2.next_work()), 1)


if __name__ == "__main__":
    unittest.main()
