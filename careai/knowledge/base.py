"""Knowledge layer: vector index, knowledge graph, rule base, conflict table."""
import json
import networkx as nx
from .. import config
from .vectors import make_index

class KnowledgeBase:
    def __init__(self, path=None):
        path = path or config.DATA_DIR / "knowledge_seed.json"
        d = json.load(open(path))
        self.interventions = {i["id"]: i for i in d["interventions"]}
        self.rules = d["rules"]
        self.conflicts = d["conflicts"]
        self.policy = d["policy_corpus"]
        self.notice = d["_notice"]
        self.vindex = make_index({i["id"]: f'{i["name"]}. {i["text"]} {" ".join(i["needs"])} {" ".join(i["conditions"])} {i["domain"]}'
                                   for i in self.interventions.values()})
        self.graph = self._build_graph(d)

    def _build_graph(self, d):
        g = nx.Graph()
        for c, syms in d["symptoms"].items():
            for s in syms:
                g.add_edge(f"cond:{c}", f"need:{s}", rel="has_symptom")
        for a, b in d["comorbid"]:
            g.add_edge(f"cond:{a}", f"cond:{b}", rel="comorbid_with")
        for i in d["interventions"]:
            for c in i["conditions"]:
                g.add_edge(f"cond:{c}", f"int:{i['id']}", rel="recommends_intervention")
            for n in i["needs"]:
                g.add_edge(f"need:{n}", f"int:{i['id']}", rel="addresses")
        return g

    def graph_scores(self, conditions, flags) -> dict[str, float]:
        """Relationship-aware proximity: 1/(1+shortest-path distance) from the student's anchor nodes."""
        anchors = [f"cond:{c}" for c in conditions] + [f"need:{f}" for f in flags]
        anchors = [a for a in anchors if a in self.graph]
        out = {i: 0.0 for i in self.interventions}
        for a in anchors:
            for node, dist in nx.single_source_shortest_path_length(self.graph, a, cutoff=4).items():
                if node.startswith("int:") and dist > 0:
                    iid = node[4:]
                    out[iid] = max(out[iid], 1.0 / dist)
        return out

    def rule_effects(self, conditions, flags):
        """Return (boost scores, blocked ids, fired rules)."""
        boost, blocked, fired = {}, {}, []
        for r in self.rules:
            w = r["when"]
            if all(c in conditions for c in w.get("conditions", [])) and \
               all(f in flags for f in w.get("flags", [])):
                fired.append(r["id"])
                for b in r["boost"]:
                    boost[b] = 1.0
                for b in r["block"]:
                    blocked[b] = r["why"]
        return boost, blocked, fired
