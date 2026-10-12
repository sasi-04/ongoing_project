"""Build data/literature.json from research PDFs (page-level provenance, de-duplicated, references stripped).
Usage: python -m scripts.ingest_pdfs /path/to/pdf_dir
The runtime never needs the PDFs: it reads the generated JSON only.
"""
import json, re, sys, pathlib
from pypdf import PdfReader

META = {  # id -> (title, short citation, role, topics)  -- taken from the CARE-AI paper's reference list
 "1": ("Agentic AI for Education: A Unified Multi-Agent Framework for Personalized Learning and Institutional Intelligence", "Mary et al. 2026", "design", ["multi-agent", "routing", "consensus"]),
 "2": ("FACET: Multi-Agent AI Supporting Teachers in Scaling Differentiated Learning for Diverse Students", "Gonnermann-Müller et al. 2026", "domain", ["multi-agent", "dyslexia", "adhd", "differentiation"]),
 "3": ("RAGTrace: Understanding and Refining Retrieval-Generation Dynamics in RAG", "Cheng et al. 2025", "design", ["rag", "retrieval", "explainability"]),
 "4": ("Using explainable machine learning and eye-tracking for diagnosing ASD and developmental language disorders", "Antolí et al. 2025", "domain", ["asd", "language", "xai"]),
 "5": ("Persona-Based Requirements Engineering for Explainable Multi-Agent Educational Systems", "Zheng et al. 2026", "design", ["persona", "hitl", "xai"]),
 "6": ("The Perceptual Gap: Why We Need Accessible XAI for Assistive Technologies", "Choudhury 2026", "design", ["xai", "accessibility"]),
 "7": ("An Explainable ML Network for Classification of ASD Using Optimal Frequency Band Identification From EEG", "Saranya & Menaka 2025", "domain", ["asd", "eeg", "shap"]),
 "8": ("AI-Powered Math Tutoring: Platform for Personalized and Adaptive Education", "Chudziak & Kostka 2025", "design", ["math", "knowledge-graph", "tutoring"]),
 "9": ("Leveraging Machine Learning for Early Autism Detection via INDT-ASD Indian Database", "Shrivastava et al. 2024", "domain", ["asd", "screening"]),
 "10": ("Inclusive Education with AI: Supporting Special Needs and Tackling Language Barriers", "Fitas 2025", "domain", ["special-needs", "language", "equity"]),
 "11": ("From Predictions to Explanations: Explainable AI for Autism Diagnosis and Identification of Critical Brain Regions", "Gupta et al. 2025", "design", ["asd", "xai", "grad-cam", "shap"]),
 "12": ("End-to-End Deployment of the Educational AI Hub for Personalized Learning and Engagement", "Sajja et al. 2025", "design", ["rag", "deployment", "metrics"]),
 "13": ("AI-Assisted Educational Framework for Floodplain Manager Certification", "Sajja et al. 2025", "design", ["rag", "qa", "vocational"]),
}
REF = re.compile(r"^\s*(\d+\.?\s*|[IVX]+\.?\s*)?(references|bibliography)\b", re.I | re.M)


def clean(t):
    t = re.sub(r"-\n(\w)", r"\1", t)          # de-hyphenate
    t = re.sub(r"[ \t]+", " ", t)
    return re.sub(r"\n{2,}", "\n\n", t).strip()


def chunks(text, size=700):
    """Pack sentences into ~size-char passages (pypdf loses paragraph breaks in 2-column papers)."""
    sents = re.split(r"(?<=[.!?])\s+(?=[A-Z])", " ".join(text.split()))
    cur, out = "", []
    for s_ in sents:
        if len(cur) + len(s_) > size and cur:
            out.append(cur); cur = ""
        cur = (cur + " " + s_).strip()
    if cur:
        out.append(cur)
    return [c for c in out if len(c) > 150 and sum(ch.isalpha() for ch in c) / len(c) > 0.65]


def main(d):
    docs, items = [], []
    for f in sorted(pathlib.Path(d).glob("[0-9]*_*.pdf"), key=lambda p: int(p.name.split("_")[0])):
        pid = f.name.split("_")[0]
        if pid not in META:
            continue
        title, short, role, topics = META[pid]
        stop = False
        r = PdfReader(str(f))
        n = 0
        for pn, page in enumerate(r.pages, 1):
            if stop:
                break
            txt = clean(page.extract_text() or "")
            m = REF.search(txt)
            if m:
                txt, stop = txt[:m.start()], True
            for c in chunks(txt):
                n += 1
                items.append({"id": f"P{pid}-p{pn}-{n}", "paper": f"P{pid}", "page": pn, "text": c})
        docs.append({"id": f"P{pid}", "title": title, "cite": short, "role": role, "topics": topics,
                     "pages": len(r.pages), "chunks": n, "file": f.name})
        print(f"P{pid}: {len(r.pages)} pages -> {n} chunks")
    out = pathlib.Path(__file__).resolve().parent.parent / "data" / "literature.json"
    out.write_text(json.dumps({"_notice": "Passages are extracted automatically from the supplied PDFs for retrieval and citation. "
                               "Papers marked role=design support CARE-AI's architecture; they are NOT clinical efficacy evidence for interventions.",
                               "papers": docs, "chunks": items}))
    print("wrote", out, len(items), "chunks")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "/mnt/project")
