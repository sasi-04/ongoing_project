"""Adaptive Agent Selection (paper Alg. 1, Eq. 1): a_i = sigmoid(w_i . x + b_i); activate if a_i >= tau.
If no agent fires, fall back to Planning only. Weights start from hand-set priors that mimic simple
relevance rules and are LEARNED from expert feedback (paper Alg. 4, Eq. 8) via the Store.
"""
import math
from .. import config
from ..schemas import CONDITIONS
from .analysis import ANALYSIS_AGENTS

FEATURES = ["n_cond", "has_med", "n_acad", "has_beh", "incidents", "has_speech", "has_vision",
            "flag_speech", "flag_vision", "flag_beh"] + [f"cond_{c}" for c in CONDITIONS]
BEH = {"anxiety", "sensory_overload", "meltdown", "elopement", "inattention", "impulsivity", "transition_difficulty"}
SPEECH = {"nonverbal", "articulation", "fluency"}

PRIORS = {  # agent -> (bias, {feature: weight})
    "medical": (-0.3, {"n_cond": 1.5, "has_med": 2.0}),
    "academic": (-0.5, {"n_acad": 2.5, "n_cond": 0.6}),
    "behavior": (-0.5, {"has_beh": 2.0, "incidents": 1.5, "flag_beh": 1.0}),
    "speech": (-1.5, {"has_speech": 2.5, "flag_speech": 2.5, "cond_speech_language": 3.0}),
    "vision": (-1.5, {"has_vision": 2.5, "flag_vision": 2.5}),
}


def featurize(case, flags) -> dict:
    f = {k: 0.0 for k in FEATURES}
    f["n_cond"] = min(len(case.conditions), 3) / 3
    f["has_med"] = float(bool(case.medical_notes))
    f["n_acad"] = min(len(case.academic), 4) / 4
    f["has_beh"] = float(bool(case.behavior_notes))
    f["incidents"] = min(case.incidents_last_30d, 10) / 10
    f["has_speech"], f["has_vision"] = float(bool(case.speech_notes)), float(bool(case.vision_notes))
    f["flag_speech"] = len(SPEECH & set(flags)) / 3
    f["flag_vision"] = float("visual_tracking" in flags)
    f["flag_beh"] = len(BEH & set(flags)) / 3
    for c in case.conditions:
        if f"cond_{c}" in f:
            f[f"cond_{c}"] = 1.0
    return f


def _sig(z):
    return 1 / (1 + math.exp(-max(-30, min(30, z))))


def get_weights(store=None):
    learned = store.router_weights() if store else {}
    return {a: learned.get(a, {"b": PRIORS[a][0], "w": {k: PRIORS[a][1].get(k, 0.0) for k in FEATURES}})
            for a in PRIORS}


def probs(x, weights):
    return {a: _sig(w["b"] + sum(w["w"].get(k, 0.0) * x[k] for k in FEATURES)) for a, w in weights.items()}


def route(case, flags, store=None, tau=config.ROUTER_THRESHOLD):
    x = featurize(case, flags)
    p = probs(x, get_weights(store))
    active = [a for a in ANALYSIS_AGENTS if p[a.name] >= tau]
    return active, {k: round(v, 3) for k, v in p.items()}, x


def sgd_update(weights, agent, x, label, eta=0.3):
    """w_i <- w_i + eta * (y - a_i) * x   (gradient step on logistic loss; paper Eq. 8)."""
    w = weights[agent]
    a = _sig(w["b"] + sum(w["w"].get(k, 0.0) * x.get(k, 0.0) for k in FEATURES))
    g = label - a
    w["b"] += eta * g
    for k in FEATURES:
        w["w"][k] = w["w"].get(k, 0.0) + eta * g * x.get(k, 0.0)
    return weights
