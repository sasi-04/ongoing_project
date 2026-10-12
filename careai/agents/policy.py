"""Policy Compliance & Bias Agent."""
import itertools


def jaccard(a, b):
    a, b = set(a), set(b)
    return 1.0 if not a | b else len(a & b) / len(a | b)


class PolicyAgent:
    name = "policy"

    def check_plan(self, plan, blocked_ids):
        checks = []
        add = lambda pid, ok, msg: checks.append({"policy": pid, "pass": bool(ok), "detail": msg})
        goals = plan["goals"]
        add("P_MEASURABLE", goals and all(g["baseline"] is not None and g["target"] is not None
                                          and g["timeframe_weeks"] and g["measure"] for g in goals),
            "All goals have baseline, target, timeframe and measure." if goals else "No goals generated; team must author goals.")
        add("P_PRESENT_LEVELS", plan["present_levels"].get("academic") or plan["present_levels"].get("behavior"),
            "Present levels recorded." if plan["present_levels"].get("academic") or plan["present_levels"].get("behavior")
            else "Insufficient data for present levels.")
        add("P_PARENT", plan["parent_involvement"] and plan.get("parent_summary"), "Parent involvement + plain-language summary present.")
        add("P_LRE", plan["least_restrictive_environment"], "LRE statement present.")
        used = {r["intervention_id"] for k in ("accommodations", "strategies", "services") for r in plan[k]}
        bad = used & set(blocked_ids)
        add("RULE_BLOCKS", not bad, "No rule-blocked interventions in plan." if not bad else f"Blocked interventions present: {sorted(bad)}")
        add("P_REVIEW", True, "Plan flagged as draft requiring human approval.")
        return checks

    def bias_audit(self, case, recommend_fn, threshold=0.9):
        """Counterfactual fairness test: change demographic attributes only; recommendations must not change.
        primary_language is excluded because language support may legitimately differ."""
        base = recommend_fn(case)
        variants = {"gender": ["female", "male", "nonbinary"], "ethnicity": ["group_a", "group_b"],
                    "ses": ["low", "high"]}
        results = []
        for attr, vals in variants.items():
            for v in vals:
                if getattr(case.demographics, attr) == v:
                    continue
                cf = case.model_copy(deep=True)
                setattr(cf.demographics, attr, v)
                results.append({"attribute": attr, "value": v, "similarity": round(jaccard(base, recommend_fn(cf)), 3)})
        worst = min((r["similarity"] for r in results), default=1.0)
        return {"method": "counterfactual demographic substitution (Jaccard similarity of recommended interventions)",
                "threshold": threshold, "worst_similarity": worst, "pass": worst >= threshold, "variants": results,
                "limits": "Detects direct demographic sensitivity only; proxy bias and outcome disparities need population-level audits."}
