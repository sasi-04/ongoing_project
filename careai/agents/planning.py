"""Planning Agent: synthesises resolved recommendations + analysis findings into a draft IEP."""
import math
from ..schemas import Goal
from . import twin
from .analysis import slope

DOMAIN_MAP = {"reading": "reading", "ela": "reading", "english": "reading", "literacy": "reading",
              "math": "math", "mathematics": "math", "writing": "writing"}


class PlanningAgent:
    name = "planning"

    def run(self, case, kb, recs, findings):
        eff = lambda r: kb.interventions.get(r.intervention_id, {}).get("effect", 0.0)
        tgt = lambda r: kb.interventions.get(r.intervention_id, {}).get("targets", [])
        goals, sims, gaps = [], {}, []
        for subj, score in case.academic.items():
            if score >= 75:
                continue
            dom = DOMAIN_MAP.get(subj.lower(), subj.lower())
            rel = {r.intervention_id: eff(r) for r in recs if dom in tgt(r)}
            hist = case.academic_history.get(subj, [])
            base_slope = max(min(slope(hist), 5.0), -5.0) if len(hist) >= 2 else 0.0
            sim = twin.what_if(score, base_slope, rel)
            sims[subj] = sim
            target = round(min(100.0, score + max(8.0, min(sim["predicted_gain"], 15.0))), 0)  # capped: twin priors are uncalibrated
            goals.append(Goal(id=f"G_{subj}", domain=dom, baseline=score, target=target, timeframe_weeks=12,
                              measure=f"{subj} curriculum-based assessment score (0-100)",
                              statement=f"By week 12, {subj} assessment score will increase from {score:.0f} to at least {target:.0f}.",
                              predicted_gain=sim["predicted_gain"]))
        if case.incidents_last_30d > 0:
            tb = math.ceil(case.incidents_last_30d * 0.5)
            goals.append(Goal(id="G_behavior", domain="behavior", baseline=case.incidents_last_30d, target=tb,
                              timeframe_weeks=12, measure="Classroom incidents per 30 days (staff log)",
                              statement=f"By week 12, classroom incidents will decrease from {case.incidents_last_30d} to {tb} or fewer per 30 days."))
        else:
            gaps.append("No behavior baseline provided; no behavior goal generated.")
        if not case.academic:
            gaps.append("No academic scores provided; no academic goals generated.")
        if "speech" in findings and findings["speech"].get("indicators"):
            gaps.append("Speech/communication goal needs a baseline from the speech-language pathologist.")

        pick = lambda cat: [r.model_dump() for r in recs if r.category == cat]
        present = {"conditions": case.conditions, "academic": case.academic,
                   "strengths": findings.get("academic", {}).get("strengths", {}),
                   "behavior": findings.get("behavior", {}).get("patterns", []),
                   "functional_notes": "Compiled from provided records; to be verified by the team."}
        return {"present_levels": present, "goals": [g.model_dump() for g in goals],
                "accommodations": pick("accommodation"), "strategies": pick("strategy"),
                "services": pick("service"),
                "parent_involvement": "Parents/guardians are invited to review and contribute to every section; a plain-language summary is provided.",
                "least_restrictive_environment": "Default placement is the general education classroom with supports; any removal requires team justification.",
                "digital_twin": sims, "data_gaps": gaps}
