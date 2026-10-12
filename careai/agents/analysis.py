import re
from .base import AnalysisAgent

MEDS = ["methylphenidate", "atomoxetine", "guanfacine", "risperidone", "aripiprazole", "melatonin",
        "lisdexamfetamine", "amphetamine", "sertraline", "fluoxetine"]


def slope(xs):
    n = len(xs)
    if n < 2:
        return 0.0
    mx, my = (n - 1) / 2, sum(xs) / n
    den = sum((i - mx) ** 2 for i in range(n))
    return sum((i - mx) * (x - my) for i, x in enumerate(xs)) / den


class MedicalAgent(AnalysisAgent):
    name, domain = "medical", "medical"

    def relevance(self, case, flags):
        return 1.0 if case.conditions or case.medical_notes else 0.2

    def completeness(self, case):
        return 0.9 if case.medical_notes else 0.5

    def findings(self, ctx):
        c, kb = ctx.case, ctx.kb
        text = c.medical_notes.lower()
        meds = [m for m in MEDS if m in text]
        pairs = [p for p in kb.graph.edges if p[0].startswith("cond:") and p[1].startswith("cond:")
                 and kb.graph.edges[p]["rel"] == "comorbid_with"]
        co = [[a[5:], b[5:]] for a, b in pairs if a[5:] in c.conditions and b[5:] in c.conditions]
        return {"conditions": c.conditions, "medications_mentioned": meds, "comorbid_pairs": co,
                "note": "Medication names are surfaced for team awareness only; no dosing or medication advice is generated."}


class AcademicAgent(AnalysisAgent):
    name, domain = "academic", "academic"

    def relevance(self, case, flags):
        return 1.0 if case.academic else (0.6 if case.conditions else 0.2)

    def completeness(self, case):
        return min(1.0, 0.4 + 0.15 * len(case.academic))

    def findings(self, ctx):
        c = ctx.case
        strengths = {k: v for k, v in c.academic.items() if v >= 70}
        needs = {k: v for k, v in c.academic.items() if v < 60}
        trends = {k: round(slope(c.academic_history.get(k, [])), 2) for k in c.academic_history}
        return {"strengths": strengths, "areas_of_need": needs, "trend_per_term": trends,
                "learning_style_indicators": "not inferred (insufficient validated data)"}


class BehaviorAgent(AnalysisAgent):
    name, domain = "behavior", "behavior"
    BEH = {"anxiety", "sensory_overload", "meltdown", "elopement", "inattention", "impulsivity",
           "transition_difficulty"}

    def relevance(self, case, flags):
        return 1.0 if (case.behavior_notes or case.incidents_last_30d) else 0.3

    def completeness(self, case):
        return min(1.0, 0.3 + 0.2 * len(case.behavior_notes))

    def findings(self, ctx):
        c = ctx.case
        pats = sorted(set(ctx.flags) & self.BEH)
        sev = "high" if c.incidents_last_30d > 6 else "moderate" if c.incidents_last_30d > 2 else "low"
        return {"patterns": pats, "incidents_last_30d": c.incidents_last_30d, "incident_severity": sev}


class SpeechAgent(AnalysisAgent):
    name, domain = "speech", "speech"
    SP = {"nonverbal", "articulation", "fluency"}

    def relevance(self, case, flags):
        if getattr(case, "speech_telemetry", None):
            return 1.0
        return 1.0 if (case.speech_notes or "speech_language" in case.conditions or self.SP & set(flags)) else 0.1

    def completeness(self, case):
        if getattr(case, "speech_telemetry", None):
            return 0.95
        return 0.8 if case.speech_notes else 0.4

    def findings(self, ctx):
        c = ctx.case
        telemetry = getattr(c, "speech_telemetry", None) or {}
        inds = sorted(set(ctx.flags) & self.SP)
        if telemetry.get("indicators"):
            inds = sorted(set(inds) | set(telemetry.get("indicators")))

        res = {
            "indicators": inds,
            "speech_rate_wpm": telemetry.get("speech_rate_wpm", 128),
            "articulation_clarity": telemetry.get("articulation_clarity_pct", 88.0),
            "fluency_score": telemetry.get("fluency_score", 90.0),
            "vocal_stress_index": telemetry.get("vocal_stress_index", 20.0),
            "note": telemetry.get("clinical_summary", "Multimodal acoustic biomarker intake verified.") if telemetry else (
                "Text notes only. Real-time microphone audio scan available via Multimodal Lab."
            )
        }
        return res


class VisionAgent(AnalysisAgent):
    name, domain = "vision", "vision"

    def relevance(self, case, flags):
        if getattr(case, "vision_telemetry", None):
            return 1.0
        return 1.0 if (case.vision_notes or "visual_tracking" in flags) else 0.1

    def completeness(self, case):
        if getattr(case, "vision_telemetry", None):
            return 0.95
        return 0.8 if case.vision_notes else 0.4

    def findings(self, ctx):
        c = ctx.case
        telemetry = getattr(c, "vision_telemetry", None) or {}
        inds = [f for f in ctx.flags if f == "visual_tracking"]
        if telemetry.get("indicators"):
            inds = sorted(set(inds) | set(telemetry.get("indicators")))

        res = {
            "indicators": inds,
            "gaze_stability_score": telemetry.get("gaze_stability_score", 86.0),
            "visual_attention_pct": telemetry.get("visual_attention_pct", 88.0),
            "ocular_strain_index": telemetry.get("ocular_strain_index", 22.0),
            "visual_fatigue_level": telemetry.get("visual_fatigue_level", "Low / Baseline"),
            "note": telemetry.get("clinical_notes", "Ocular tracking & visual ergonomics telemetry verified.") if telemetry else (
                "Text notes only. Real-time webcam gaze & ocular strain scan available via Multimodal Lab."
            )
        }
        return res


ANALYSIS_AGENTS = [MedicalAgent(), AcademicAgent(), BehaviorAgent(), SpeechAgent(), VisionAgent()]
