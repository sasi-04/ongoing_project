import os, tempfile, pathlib
os.environ["CAREAI_LLM"] = "off"
os.environ["CAREAI_DB"] = str(pathlib.Path(tempfile.mkdtemp()) / "api.db")
import pytest
from fastapi.testclient import TestClient
from careai.store import Store
from careai.orchestrator import Orchestrator
from careai.schemas import StudentCase
from careai.agents.router import route
from careai.knowledge.retrieval import extract_flags
from careai.privacy import scrub
from careai.agents import twin, risk

CASE = dict(student_id="T1", age=10, conditions=["adhd", "dyslexia"], academic={"reading": 48, "math": 72},
            academic_history={"reading": [55, 52, 48]}, behavior_notes=["loses focus", "anxious reading aloud"],
            incidents_last_30d=4, attendance_rate=0.9)


@pytest.fixture()
def orch():
    return Orchestrator(Store(pathlib.Path(tempfile.mkdtemp()) / "t.db"))


def test_router_skips_irrelevant_agents():
    c = StudentCase(**CASE)
    active, _, _ = route(c, extract_flags(c))
    names = [a.name for a in active]
    assert "speech" not in names and "academic" in names


def test_rule_blocks_timed_drills_for_anxious_dyslexic(orch):
    plan = orch.run(StudentCase(**CASE))
    used = {r["intervention_id"] for k in ("accommodations", "strategies", "services") for r in plan[k]}
    assert "I_TIMED_DRILLS" not in used and "I_TIMED_DRILLS" in plan["blocked_by_rules"]


def test_no_condition_leakage(orch):
    plan = orch.run(StudentCase(**CASE))
    used = {r["intervention_id"] for k in ("accommodations", "strategies", "services") for r in plan[k]}
    assert not used & {"I_AAC", "I_VIS_SCHED", "I_MATH_CRA"}  # ASD / math-SLD items must not appear


def test_consensus_synthesises_conflicts(orch):
    plan = orch.run(StudentCase(**CASE))
    assert any(d["outcome"] == "synthesis" for d in plan["consensus"]["debate"])


def test_every_item_explained_and_goals_measurable(orch):
    plan = orch.run(StudentCase(**CASE))
    n = sum(len(plan[k]) for k in ("accommodations", "strategies", "services"))
    assert len(plan["explanations"]) == n
    assert all(c["pass"] for c in plan["policy_checks"]) and plan["draft"] is True


def test_bias_audit_detects_injected_bias(orch):
    c = StudentCase(**CASE)
    biased = lambda case: ["A", "B"] if case.demographics.gender != "male" else ["A", "C"]
    assert orch.policy.bias_audit(c, biased)["pass"] is False
    assert orch.policy.bias_audit(c, orch.recommend_ids)["pass"] is True


def test_scrub_removes_pii():
    s = scrub("Call Dr. Smith at 555-123-4567 or a@b.com on 01/02/2024")
    assert "Smith" not in s and "555" not in s and "@" not in s and "2024" not in s


def test_twin_and_risk_sanity():
    assert twin.simulate(50, 0, [0.4])["mean"] > twin.simulate(50, 0, [])["mean"]
    c = StudentCase(**CASE)
    hi = risk.predict(c.model_copy(update={"incidents_last_30d": 10, "attendance_rate": 0.6}), [])
    lo = risk.predict(StudentCase(student_id="x", age=9), [])
    assert hi["behavioral_risk"]["probability"] > lo["behavioral_risk"]["probability"]


def test_feedback_reweights_retrieval(orch):
    from careai.agents.feedback import FeedbackLearningAgent
    fb = FeedbackLearningAgent(orch.retriever.kb and orch.store)
    for _ in range(3):
        fb.record("p", "i", "I_TTS", "reject", None, "teacher")
    assert orch.store.weights()["I_TTS"] < 1.0
    assert fb.record("p", "i", "I_TTS", "accept", None, "parent")["weight_updated"] is False


def _login(cl, name, role, students=()):
    from careai import auth
    from careai.api import store
    if not store.get_user(name):
        store.add_user(name, auth.hash_password("correct-horse-battery"), role, list(students))
    t = cl.post("/auth/login", json={"username": name, "password": "correct-horse-battery"}).json()["token"]
    return {"Authorization": f"Bearer {t}"}


def test_api_hitl_flow():
    from careai.api import app
    cl = TestClient(app)
    T, C, P, A = (_login(cl, "t1", "teacher"), _login(cl, "c1", "clinician"),
                  _login(cl, "p1", "parent", ["T1"]), _login(cl, "a1", "admin"))
    p = cl.post("/cases", json=CASE, headers=T).json()
    pid = p["plan_id"]
    assert cl.post("/cases", json=CASE, headers=P).status_code == 403
    assert cl.get(f"/plans/{pid}").status_code == 401                       # no token
    pv = cl.get(f"/plans/{pid}", headers=P).json()
    assert "agent_findings" not in pv and "goals" in pv                      # parent view is restricted
    assert cl.post(f"/plans/{pid}/approve", headers=T).status_code == 409    # undecided items
    items = [x for k in ("accommodations", "strategies", "services") for x in p[k]]
    for it in items:
        assert cl.post(f"/plans/{pid}/review", json={"item_id": it["id"], "decision": "accept"}, headers=C).status_code == 200
    assert cl.post(f"/plans/{pid}/approve", headers=P).status_code == 403
    assert cl.post(f"/plans/{pid}/approve", headers=C).json()["status"] == "approved"
    assert len(cl.get(f"/plans/{pid}/audit", headers=A).json()) >= 3
    assert cl.get("/audit/verify", headers=A).json()["intact"] is True


def test_parent_cannot_see_other_children_and_login_throttle():
    from careai.api import app
    cl = TestClient(app)
    T = _login(cl, "t2", "teacher")
    other = dict(CASE, student_id="OTHER")
    pid = cl.post("/cases", json=other, headers=T).json()["plan_id"]
    P = _login(cl, "p2", "parent", ["T1"])
    assert cl.get(f"/plans/{pid}", headers=P).status_code == 403
    for _ in range(5):
        cl.post("/auth/login", json={"username": "t2", "password": "wrong-wrong-wrong"})
    assert cl.post("/auth/login", json={"username": "t2", "password": "correct-horse-battery"}).status_code == 429


def test_encryption_at_rest_and_audit_tamper_detection(orch):
    import sqlite3, json
    c = StudentCase(**CASE)
    pid = orch.store.save_plan(c, orch.run(c))
    raw = orch.store.db.execute("SELECT case_json, plan_json FROM plans WHERE id=?", (pid,)).fetchone()
    assert "adhd" not in raw[0] and "goals" not in raw[1]                    # ciphertext only
    orch.store.log(pid, "u", "teacher", "a"); orch.store.log(pid, "u", "teacher", "b")
    assert orch.store.verify_audit()["intact"] is True
    orch.store.db.execute("UPDATE audit SET action='tampered' WHERE id=1"); orch.store.db.commit()
    assert orch.store.verify_audit()["intact"] is False


def test_router_learns_from_rejections_and_skips_on_policy_fail(orch):
    from careai.agents.feedback import FeedbackLearningAgent
    from careai.agents import router
    c = StudentCase(**CASE)
    plan = orch.run(c)
    fb = FeedbackLearningAgent(orch.store)
    item = next(r for k in ("accommodations", "strategies", "services") for r in plan[k] if r["source_agent"] in router.PRIORS)
    ag = item["source_agent"]
    before = router.probs(plan["router_features"], router.get_weights(orch.store))[ag]
    for _ in range(4):
        r = fb.record("p", item["id"], item["intervention_id"], "reject", None, "teacher", plan=plan)
    after = router.probs(plan["router_features"], router.get_weights(orch.store))[ag]
    assert r["router_updated"] and after < before
    bad = dict(plan, bias_audit={"pass": False})
    n = orch.store.replay_size()
    assert fb.record("p", item["id"], item["intervention_id"], "reject", None, "teacher", plan=bad)["router_updated"] is False
    assert orch.store.replay_size() == n


def test_paper_formulas():
    from careai.knowledge.retrieval import difficulty_from_similarity
    assert difficulty_from_similarity(1.0)[2] == 3 and difficulty_from_similarity(0.0)[2] == 10   # Eq. 2-3
    assert difficulty_from_similarity(0.5)[2] == 7


def test_literature_search(orch):
    hits = orch.library.search("explainable AI SHAP autism", k=3)
    assert hits and hits[0]["page"] >= 1 and hits[0]["paper"].startswith("P")
