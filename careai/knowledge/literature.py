"""Research library built from the supplied PDFs (see scripts/ingest_pdfs.py)."""
import json
from .. import config
from .vectors import make_index

# Component -> supporting papers, taken from the CARE-AI paper's own citations (main.pdf)
DESIGN_MAP = {
    "adaptive_agent_selection": ["P1"], "adaptive_rag": ["P3", "P12"], "knowledge_graph_retrieval": ["P8", "P12"],
    "consensus": ["P1"], "explainability_shap_gradcam": ["P7", "P11", "P4"], "accessible_explanations": ["P6"],
    "human_in_the_loop_personas": ["P5"], "policy_and_bias": ["P10"], "risk_and_screening_models": ["P9", "P7"],
    "differentiated_instruction_agents": ["P2"], "evaluation_metrics": ["P12", "P13"]}


class Library:
    def __init__(self, path=None):
        path = path or config.DATA_DIR / "literature.json"
        try:
            d = json.load(open(path))
        except FileNotFoundError:
            d = {"_notice": "literature.json missing: run scripts/ingest_pdfs.py", "papers": [], "chunks": []}
        self.notice, self.papers = d["_notice"], {p["id"]: p for p in d["papers"]}
        self.chunks = {c["id"]: c for c in d["chunks"]}
        self.index = make_index({i: c["text"] for i, c in self.chunks.items()}) if self.chunks else None

    def search(self, query, k=5, role=None, min_score=0.0):
        if not self.index:
            return []
        sc = self.index.scores(query)
        out = []
        for cid, s in sorted(sc.items(), key=lambda x: -x[1]):
            c = self.chunks[cid]; p = self.papers[c["paper"]]
            if role and p["role"] != role:
                continue
            if s < min_score:
                break
            out.append({"score": round(s, 3), "paper": c["paper"], "cite": p["cite"], "title": p["title"],
                        "page": c["page"], "role": p["role"], "snippet": c["text"][:400]})
            if len(out) >= k:
                break
        return out
