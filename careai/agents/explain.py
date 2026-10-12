"""Explainability Agent: confidence, evidence, plain-language rationale, transparent attribution.

Method note: SHAP/LIME/Grad-CAM need trained models. The current components are rule/retrieval-based,
so attribution is exact and additive (retrieval components x fusion weights). SHAP plugs in once the
risk or router models are learned.
"""
from .. import config, llm


def explain(case, flags, rec, rules_fired, kb):
    w = config.FUSION_WEIGHTS
    # Fusion s(e)=a*s_vec+b*s_kg+g*s_rule is additive, so exact Shapley values (zero baseline) are w_f*s_f.
    contrib = {k: round(w[k] * rec.components.get(k, 0.0), 3) for k in w}
    conf_shapley = round(sum(abs(v) for v in contrib.values()) / len(contrib), 3)  # paper Eq. 6
    itv = kb.interventions.get(rec.intervention_id)
    matched_cond = [c for c in case.conditions if itv and c in itv["conditions"]]
    matched_need = [n for n in flags if itv and n in itv["needs"]]
    reasons = []
    if matched_cond:
        reasons.append("the student's documented condition(s): " + ", ".join(matched_cond))
    if matched_need:
        reasons.append("observed needs: " + ", ".join(matched_need))
    if rec.intervention_id.startswith("SYN:"):
        reasons.append("it reconciles two competing recommendations so both needs are met")
    if rec.components.get("agent_agreement", 1) > 1:
        reasons.append(f"{int(rec.components['agent_agreement'])} agents independently proposed it")
    rationale = "Recommended because of " + ("; ".join(reasons) if reasons else "retrieved supporting evidence") + "."
    text = None
    if llm.available():
        text = llm.generate(
            "Rewrite in 2 plain sentences for a teacher. Use ONLY these facts, add nothing.\n"
            f"Recommendation: {rec.text}\nFacts: {rationale}",
            system="You explain special-education recommendations. Never invent facts or citations.")
    return {"recommendation_id": rec.id, "confidence": rec.confidence, "confidence_shapley_eq6": conf_shapley,
            "rationale": text or rationale, "rationale_source": "llm" if text else "template",
            "attribution": contrib, "attribution_method": "exact Shapley values of the additive fusion model", "feedback_weight": rec.components.get("feedback_weight", 1.0),
            "evidence": rec.evidence, "rules_fired": rules_fired,
            "evidence_quality": "seed-illustrative: verify against curated sources"}
