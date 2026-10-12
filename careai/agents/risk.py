"""Risk Prediction Agent: transparent additive logistic model.

Weights are UNCALIBRATED PRIORS chosen for interpretability. Replace with a model trained on
longitudinal outcomes (then SHAP applies); the additive contributions below are exact for this model.
"""
import math
from .analysis import slope

W_ACAD = {"low_scores": 2.5, "decline": 1.5, "absence": 1.5, "incidents": 0.5, "comorbidity": 0.4}
W_BEH = {"incidents": 3.0, "escalation_flags": 1.2, "comorbidity": 0.4, "absence": 0.5}
BIAS = {"academic": -2.0, "behavioral": -2.0}


def _clip(x):
    return max(0.0, min(1.0, x))


def features(case, flags):
    scores = list(case.academic.values())
    low = sum(max(0, (60 - s) / 60) for s in scores) / len(scores) if scores else 0.0
    sl = [slope(v) for v in case.academic_history.values() if len(v) >= 2]
    decline = _clip(-min(sl) / 5) if sl else 0.0
    absence = _clip((1 - case.attendance_rate) / 0.2) if case.attendance_rate is not None else 0.0
    return {"low_scores": _clip(low), "decline": decline, "absence": absence,
            "incidents": _clip(case.incidents_last_30d / 10),
            "escalation_flags": _clip(len({"meltdown", "elopement", "sensory_overload"} & set(flags)) / 3),
            "comorbidity": _clip((len(case.conditions) - 1) / 2)}


def _score(feats, weights, bias):
    contrib = {k: round(w * feats.get(k, 0.0), 3) for k, w in weights.items()}
    p = 1 / (1 + math.exp(-(bias + sum(contrib.values()))))
    level = "low" if p < 0.33 else "moderate" if p < 0.66 else "high"
    return {"probability": round(p, 3), "level": level,
            "top_factors": sorted(contrib.items(), key=lambda x: -x[1])[:3], "contributions": contrib}


TRIGGERS = {"high": "Convene the team within 2 weeks; review plan intensity and supports.",
            "moderate": "Add a monitoring checkpoint at 4-6 weeks.",
            "low": "Continue routine monitoring."}


def predict(case, flags):
    f = features(case, flags)
    a, b = _score(f, W_ACAD, BIAS["academic"]), _score(f, W_BEH, BIAS["behavioral"])
    return {"academic_risk": a, "behavioral_risk": b, "features": {k: round(v, 3) for k, v in f.items()},
            "intervention_trigger": {"academic": TRIGGERS[a["level"]], "behavioral": TRIGGERS[b["level"]]},
            "caveat": "Uncalibrated prior model; do not use as a standalone predictor."}
