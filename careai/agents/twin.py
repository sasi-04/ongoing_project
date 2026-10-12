"""Student Digital Twin: simple stochastic trajectory model for what-if intervention simulation.

IMPORTANT: effect sizes in the seed KB are ASSUMED PRIORS, so outputs are illustrative until
calibrated against real longitudinal outcome data. Output always says so.
"""
import random, statistics


def simulate(baseline: float, base_slope_per_term: float, effects: list[float], weeks=12, n=300, seed=7):
    rnd = random.Random(seed)
    eff_sum = min(sum(effects), 1.0)
    finals = []
    for _ in range(n):
        lvl = baseline
        scale = max(rnd.gauss(1.0, 0.3), 0.0)  # uncertainty about true effect size
        for _w in range(weeks):
            gain = (base_slope_per_term / 12.0) + 5.0 * eff_sum * scale * (100 - lvl) / 100.0
            lvl = min(100.0, lvl + gain + rnd.gauss(0, 0.5))
        finals.append(lvl)
    finals.sort()
    return {"baseline": baseline, "mean": round(statistics.mean(finals), 1),
            "p10": round(finals[int(0.1 * n)], 1), "p90": round(finals[int(0.9 * n)], 1)}


def what_if(baseline, base_slope, effects_by_intervention: dict[str, float], weeks=12):
    """Return predicted gain with no intervention, all interventions, and each one alone."""
    none = simulate(baseline, base_slope, [], weeks)
    allv = simulate(baseline, base_slope, list(effects_by_intervention.values()), weeks)
    solo = {k: round(simulate(baseline, base_slope, [v], weeks)["mean"] - none["mean"], 1)
            for k, v in effects_by_intervention.items()}
    return {"no_intervention": none, "with_plan": allv,
            "predicted_gain": round(allv["mean"] - none["mean"], 1), "solo_gain": solo,
            "caveat": "Illustrative: effect sizes are assumed priors, not calibrated to real outcomes."}
