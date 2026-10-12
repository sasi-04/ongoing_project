"""Adaptive, hybrid retrieval: difficulty estimation -> depth/source selection -> fusion -> (multi-pass)."""
import math
from dataclasses import dataclass, field
from .. import config
from .base import KnowledgeBase


def extract_flags(case) -> list[str]:
    text = " ".join([case.medical_notes, case.speech_notes, case.vision_notes, *case.behavior_notes]).lower()
    return sorted(f for f, kws in config.FLAG_KEYWORDS.items() if any(k in text for k in kws))


K_MIN, K_MAX = 3, 10


def difficulty_from_similarity(max_sim: float):
    """Paper Eq. 2-3: d(q) = 1 - max_k sim(q, D_k);  k*(q) = k_min + ceil((k_max - k_min) * d(q))."""
    d = max(0.0, min(1.0, 1.0 - max_sim))
    k = K_MIN + math.ceil((K_MAX - K_MIN) * d)
    level = "low" if d < 0.4 else "medium" if d < 0.7 else "high"
    return level, round(d, 3), k


@dataclass
class Hit:
    intervention_id: str
    score: float
    components: dict
    blocked_reason: str = ""


@dataclass
class RetrievalResult:
    hits: list
    difficulty: str
    difficulty_score: float
    k: int
    sources: tuple
    passes: int
    fired_rules: list = field(default_factory=list)
    blocked: dict = field(default_factory=dict)


class AdaptiveRetriever:
    def __init__(self, kb: KnowledgeBase, feedback_weights=None):
        self.kb = kb
        self.fw = feedback_weights or (lambda: {})

    def _query(self, case, flags, domain):
        parts = [" ".join(case.conditions), " ".join(flags), domain or ""]
        return " ".join(parts)

    def retrieve(self, case, domain=None, flags=None) -> RetrievalResult:
        flags = flags if flags is not None else extract_flags(case)
        level, dscore, k = difficulty_from_similarity(self.kb.vindex.max_sim(self._query(case, flags, domain)))
        sources = ("vector", "rule") if level == "low" else ("vector", "graph", "rule")
        passes = 1
        hits, fired, blocked = self._run(case, flags, domain, k, sources)
        # multi-pass: weak top evidence -> widen depth and add graph source
        if (not hits or hits[0].score < 0.25) and passes < 2:
            passes, k, sources = 2, k + 4, ("vector", "graph", "rule")
            hits, fired, blocked = self._run(case, flags, domain, k, sources)
        return RetrievalResult(hits, level, dscore, k, sources, passes, fired, blocked)

    def _run(self, case, flags, domain, k, sources):
        kb, W = self.kb, config.FUSION_WEIGHTS
        v = kb.vindex.scores(self._query(case, flags, domain)) if "vector" in sources else {}
        g = kb.graph_scores(case.conditions, flags) if "graph" in sources else {}
        boost, blocked, fired = kb.rule_effects(case.conditions, flags) if "rule" in sources \
            else ({}, {}, [])
        vmax = max(v.values(), default=0) or 1.0
        fw = self.fw()
        scored = []
        for iid, itv in kb.interventions.items():
            if domain and itv["domain"] != domain:
                continue
            if iid in blocked:
                continue
            comp = {"vector": v.get(iid, 0) / vmax, "graph": g.get(iid, 0.0), "rule": boost.get(iid, 0.0)}
            base = sum(W[s] * comp[s] for s in comp if s in sources)
            # condition-specific interventions require a condition match; condition-agnostic
            # ones (empty list) apply when one of their needs is flagged
            applicable = any(c in case.conditions for c in itv["conditions"]) if itv["conditions"] \
                else any(n in flags for n in itv["needs"])
            if not applicable:
                continue
            w = fw.get(iid, 1.0)
            comp["feedback_weight"] = w
            scored.append(Hit(iid, round(min(base * w, 1.0), 4), {k_: round(x, 3) for k_, x in comp.items()}))
        scored.sort(key=lambda h: -h.score)
        scored = [h for h in scored if h.score > 0.05][:k]
        return scored, fired, blocked
