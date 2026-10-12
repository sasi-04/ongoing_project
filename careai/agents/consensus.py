"""Consensus Agent: dedupe, detect topic conflicts, structured evidence-weighted debate, resolution."""
from collections import defaultdict
from ..schemas import Recommendation
from .base import EXPERTISE


class ConsensusAgent:
    name = "consensus"

    def run(self, kb, recs: list[Recommendation]):
        # 1) merge duplicates: same intervention proposed by several agents -> keep best, boost for agreement
        by_int = defaultdict(list)
        for r in recs:
            by_int[r.intervention_id].append(r)
        merged = []
        for iid, rs in by_int.items():
            best = max(rs, key=lambda r: r.confidence)
            best = best.model_copy(deep=True)
            if len(rs) > 1:
                best.confidence = round(min(1.0, best.confidence + 0.05 * (len(rs) - 1)), 3)
                best.components["agent_agreement"] = len(rs)
            merged.append(best)

        # 2) detect conflicts by topic
        by_topic = defaultdict(list)
        for r in merged:
            by_topic[r.topic].append(r)
        debate, final, dropped = [], [], []
        conflict_defs = {c["topic"]: c for c in kb.conflicts}
        for topic, rs in by_topic.items():
            stances = defaultdict(list)
            for r in rs:
                stances[r.stance].append(r)
            cdef = conflict_defs.get(topic)
            if not cdef or len(stances) < 2:
                final.extend(rs)
                continue
            # 3) evidence-weighted voting
            support = {}
            for st, srs in stances.items():
                support[st] = round(sum(r.confidence * EXPERTISE[r.source_agent].get(
                    kb.interventions[r.intervention_id]["domain"], 0.3) for r in srs), 3)
            ranked = sorted(support.items(), key=lambda x: -x[1])
            (w, ws), (l, ls) = ranked[0], ranked[1]
            margin = round((ws - ls) / (ws + ls), 3) if ws + ls else 0.0
            positions = [{"stance": st, "agents": sorted({r.source_agent for r in srs}),
                          "support": support[st],
                          "argument": cdef["stances"].get(st, st) + ": " + srs[0].text}
                         for st, srs in stances.items()]
            syn = cdef.get("synthesis")
            if syn and margin < 0.25:  # contested -> adopt a synthesis that satisfies both positions
                allrs = [r for srs in stances.values() for r in srs]
                final.append(Recommendation(
                    id=f"consensus:{topic}", intervention_id=f"SYN:{topic}", text=syn["text"],
                    category=allrs[0].category, topic=topic, stance=syn["stance"],
                    source_agent="consensus",
                    confidence=round(sum(r.confidence for r in allrs) / len(allrs), 3),
                    components={"synthesis_of": [r.intervention_id for r in allrs]},
                    evidence=[e for r in allrs for e in r.evidence], status="resolved"))
                dropped.extend(r.intervention_id for r in allrs)
                outcome = "synthesis"
            else:
                for st, srs in stances.items():
                    if st == w:
                        for r in srs:
                            r.status = "resolved"
                        final.extend(srs)
                    else:
                        dropped.extend(r.intervention_id for r in srs)
                outcome = f"winner:{w}"
            debate.append({"topic": topic, "positions": positions, "vote_margin": margin,
                           "outcome": outcome,
                           "rationale": f"Confidence-weighted, expertise-weighted vote ({dict(ranked)}); "
                                        f"margin {margin}. " + ("Close vote with a defined synthesis, so both needs are met."
                                                                 if outcome == "synthesis" else "Clear winner adopted.")})
        final.sort(key=lambda r: -r.confidence)
        return final, debate, dropped
