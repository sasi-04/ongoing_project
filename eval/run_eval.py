"""Evaluation harness for the success criteria in the project plan.

Metrics: agreement with expert plans (recall & Jaccard of intervention IDs), retrieval precision/recall,
latency, bias-audit pass rate, policy pass rate. Acceptance rate / user satisfaction come from live
HITL feedback (/feedback/stats) and surveys, not from this script.
Run: python -m eval.run_eval [path/to/cases.json] [all|train|val|test]
"""
import json, sys, tempfile, pathlib, statistics
from careai.store import Store
from careai.orchestrator import Orchestrator
from careai.schemas import StudentCase
from careai.knowledge.retrieval import AdaptiveRetriever, extract_flags

TARGETS = {"agreement_recall": 0.80, "retrieval_precision": 0.85, "retrieval_recall": 0.85, "latency_s": 120}


def plan_ids(plan):
    ids = set()
    for k in ("accommodations", "strategies", "services"):
        for r in plan[k]:
            ids.update(r["components"].get("synthesis_of", [r["intervention_id"]]) if r["intervention_id"].startswith("SYN:")
                       else [r["intervention_id"]])
    return ids


def in_split(sid, split):
    """Deterministic 60/20/20 train/val/test split by hash of student id. Report ONLY on test, and never tune on it."""
    import hashlib
    b = int(hashlib.sha1(sid.encode()).hexdigest(), 16) % 10
    return {"train": b < 6, "val": 6 <= b < 8, "test": b >= 8, "all": True}[split]


def main(path, split="all"):
    data = json.load(open(path))
    data["cases"] = [c for c in data["cases"] if in_split(c["case"]["student_id"], split)]
    orch = Orchestrator(Store(pathlib.Path(tempfile.mkdtemp()) / "eval.db"))
    rows = []
    for item in data["cases"]:
        case = StudentCase(**item["case"])
        plan = orch.run(case)
        got, exp, rel = plan_ids(plan), set(item["expert_plan_ids"]), set(item["relevant_ids"])
        flags = extract_flags(case)
        retrieved = {h.intervention_id for h in orch.retriever.retrieve(case, flags=flags).hits}
        prec_a = len(got & exp) / len(got) if got else 0.0
        rec_a = len(got & exp) / len(exp)
        rows.append({"id": case.student_id, "conditions": list(case.conditions),
                     "agreement_f1": (2 * prec_a * rec_a / (prec_a + rec_a)) if prec_a + rec_a else 0.0,
                     "agreement_recall": len(got & exp) / len(exp),
                     "agreement_jaccard": len(got & exp) / len(got | exp),
                     "retrieval_precision": len(retrieved & rel) / len(retrieved) if retrieved else 0,
                     "retrieval_recall": len(retrieved & rel) / len(rel),
                     "latency_s": plan["timings_s"]["total"],
                     "bias_pass": plan["bias_audit"]["pass"],
                     "policy_pass": all(c["pass"] for c in plan["policy_checks"])})
    keys = ["agreement_recall", "agreement_f1", "agreement_jaccard", "retrieval_precision", "retrieval_recall", "latency_s"]
    summary = {k: round(statistics.mean(r[k] for r in rows), 3) for k in keys}
    summary["bias_pass_rate"] = sum(r["bias_pass"] for r in rows) / len(rows)
    summary["policy_pass_rate"] = sum(r["policy_pass"] for r in rows) / len(rows)
    print(data.get("_notice", ""))
    for r in rows:
        print({k: (round(v, 2) if isinstance(v, float) else v) for k, v in r.items() if k != "conditions"})
    # per-condition reporting (paper Sec. V-G): a good average can hide a weak condition
    print("PER CONDITION (mean over cases containing the condition)")
    for c in sorted({c for r in rows for c in r["conditions"]}):
        sub = [r for r in rows if c in r["conditions"]]
        print(f"  {c:16s} n={len(sub)} " + " ".join(f"{k}={statistics.mean(r[k] for r in sub):.2f}" for k in
              ("agreement_recall", "agreement_f1", "retrieval_precision", "retrieval_recall")))
    print("SUMMARY", summary)
    for k, t in TARGETS.items():
        ok = summary[k] <= t if k == "latency_s" else summary[k] >= t
        print(f"  target {k} {'<=' if k=='latency_s' else '>='} {t}: {'MET' if ok else 'NOT MET'}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "data/synthetic_cases.json", sys.argv[2] if len(sys.argv) > 2 else "all")
