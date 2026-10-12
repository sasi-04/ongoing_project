from dataclasses import dataclass
from ..schemas import AgentOutput, Recommendation


@dataclass
class Context:
    case: object
    kb: object
    retriever: object
    flags: list


# How much each agent's vote counts per intervention domain (used by the Consensus Agent)
EXPERTISE = {
    "medical": {"medical": 1.0, "behavior": 0.6, "academic": 0.3, "speech": 0.4, "vision": 0.3},
    "academic": {"academic": 1.0, "behavior": 0.4, "speech": 0.3, "vision": 0.4, "medical": 0.2},
    "behavior": {"behavior": 1.0, "academic": 0.5, "speech": 0.4, "vision": 0.2, "medical": 0.3},
    "speech": {"speech": 1.0, "academic": 0.4, "behavior": 0.4, "vision": 0.1, "medical": 0.3},
    "vision": {"vision": 1.0, "academic": 0.5, "behavior": 0.2, "speech": 0.1, "medical": 0.3},
}


class Agent:
    name = "agent"
    domain = None

    def relevance(self, case, flags) -> float:  # used by the router
        return 1.0

    def run(self, ctx: Context) -> AgentOutput:
        raise NotImplementedError


class AnalysisAgent(Agent):
    """Retrieves domain evidence via Adaptive RAG and converts hits into scored recommendations."""

    def completeness(self, case) -> float:
        return 0.7

    def findings(self, ctx: Context) -> dict:
        return {}

    def run(self, ctx: Context) -> AgentOutput:
        res = ctx.retriever.retrieve(ctx.case, domain=self.domain, flags=ctx.flags)
        comp = self.completeness(ctx.case)
        recs = []
        for h in res.hits:
            itv = ctx.kb.interventions[h.intervention_id]
            recs.append(Recommendation(
                id=f"{self.name}:{h.intervention_id}", intervention_id=h.intervention_id,
                text=itv["text"], category=itv["category"], topic=itv["topic"], stance=itv["stance"],
                source_agent=self.name, confidence=round(h.score * (0.5 + 0.5 * comp), 3),
                components=h.components,
                evidence=[{"id": h.intervention_id, "title": itv["name"], "snippet": itv["text"],
                           "source": ctx.kb.notice[:60] + "...", "kind": "knowledge_base"}]))
        f = self.findings(ctx)
        f["retrieval"] = {"difficulty": res.difficulty, "k": res.k, "sources": list(res.sources),
                          "passes": res.passes, "rules_fired": res.fired_rules,
                          "blocked": res.blocked}
        conf = round(sum(r.confidence for r in recs) / len(recs), 3) if recs else 0.0
        return AgentOutput(agent=self.name, findings=f, recommendations=recs, confidence=conf)
