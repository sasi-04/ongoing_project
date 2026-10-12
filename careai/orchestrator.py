"""AI Orchestration layer: runs the CARE-AI pipeline end to end."""
import time
from .knowledge.base import KnowledgeBase
from .knowledge.retrieval import AdaptiveRetriever, extract_flags
from .agents.base import Context
from .agents.router import route
from .knowledge.literature import Library
from .agents.consensus import ConsensusAgent
from .agents.planning import PlanningAgent
from .agents.risk import predict as predict_risk
from .agents.explain import explain
from .agents.policy import PolicyAgent
from .agents.parent import summarise
from .privacy import scrub
from .schemas import StudentCase


class Orchestrator:
    def __init__(self, store, kb=None):
        self.store, self.kb = store, kb or KnowledgeBase()
        self.retriever = AdaptiveRetriever(self.kb, store.weights)
        self.consensus, self.planner, self.policy = ConsensusAgent(), PlanningAgent(), PolicyAgent()
        self.library = Library()

    @staticmethod
    def sanitize(case: StudentCase) -> StudentCase:
        c = case.model_copy(deep=True)
        c.medical_notes, c.speech_notes, c.vision_notes = map(scrub, (c.medical_notes, c.speech_notes, c.vision_notes))
        c.behavior_notes = [scrub(n) for n in c.behavior_notes]
        return c

    def _analyse(self, case):
        flags = extract_flags(case)
        ctx = Context(case, self.kb, self.retriever, flags)
        active, rscores, x = route(case, flags, self.store)
        outs = [a.run(ctx) for a in active]
        recs = [r for o in outs for r in o.recommendations]
        final, debate, dropped = self.consensus.run(self.kb, recs)
        return flags, active, rscores, outs, final, debate, dropped, x

    def recommend_ids(self, case):
        _, _, _, _, final, _, _, _ = self._analyse(case)
        return [r.intervention_id for r in final]

    def run(self, case: StudentCase) -> dict:
        t0, stages = time.time(), {}
        mark = lambda k, t: stages.__setitem__(k, round(time.time() - t, 3))
        case = self.sanitize(case)

        t = time.time()
        flags, active, rscores, outs, final, debate, dropped, rx = self._analyse(case)
        mark("route_analyse_consensus", t)
        findings = {o.agent: o.findings for o in outs}
        fired = sorted({r for o in outs for r in o.findings["retrieval"]["rules_fired"]})
        blocked = {}
        for o in outs:
            blocked.update(o.findings["retrieval"]["blocked"])

        t = time.time()
        plan = self.planner.run(case, self.kb, final, findings); mark("planning", t)
        t = time.time()
        risk = predict_risk(case, flags); mark("risk", t)
        t = time.time()
        expl = [explain(case, flags, r, fired, self.kb) for r in final]; mark("explainability", t)

        plan.update({
            "student_id": case.student_id, "status": "pending_review", "draft": True,
            "flags": flags,
            "router_features": rx,
            "routing": {"scores": rscores, "fallback_planning_only": not active, "active": [a.name for a in active],
                        "skipped": [n for n, s in rscores.items() if n not in [a.name for a in active]]},
            "agent_findings": findings,
            "agent_confidence": {o.agent: o.confidence for o in outs},
            "consensus": {"debate": debate, "superseded_interventions": dropped},
            "risk": risk, "explanations": expl,
            "blocked_by_rules": blocked,
            "knowledge_notice": self.kb.notice,
            "background_reading": self.library.search(
                " ".join(case.conditions) + " " + " ".join(flags) + " education support", k=3, role="domain", min_score=0.1),
            "background_reading_note": "Auto-matched passages from the supplied papers for context only; NOT clinical evidence for any recommendation.",
        })
        t = time.time()
        plan["parent_summary"] = summarise(case, plan, self.kb); mark("parent_comm", t)
        t = time.time()
        plan["policy_checks"] = self.policy.check_plan(plan, blocked.keys())
        plan["bias_audit"] = self.policy.bias_audit(case, self.recommend_ids); mark("policy_bias", t)
        stages["total"] = round(time.time() - t0, 3)
        plan["timings_s"] = stages
        plan["llm_used"] = any(e["rationale_source"] == "llm" for e in expl)
        return plan
