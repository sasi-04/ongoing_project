"""Feedback Learning Agent (paper Alg. 4): human-in-the-loop continual learning.

On each review: (1) if policy/bias checks failed -> flag, no learning ("return unchanged");
(2) store (x, y, delta) in a replay buffer; (3) gradient step on the router weights of the proposing agent;
(4) bounded multiplicative update of the intervention's retrieval weight; (5) periodic replay of a minibatch
(experience replay limits forgetting). Only teacher/clinician/therapist feedback is learned from.
"""
from .. import config
from . import router

FACTOR = {"accept": 1.05, "edit": 0.97, "reject": 0.80}
LABEL = {"accept": 1.0, "reject": 0.0}  # edit = partial signal -> no router gradient
LEARNING_ROLES = {"teacher", "clinician", "therapist"}
REPLAY_EVERY, REPLAY_BATCH = 20, 16


class FeedbackLearningAgent:
    name = "feedback_learning"

    def __init__(self, store):
        self.store = store

    def record(self, plan_id, item_id, intervention_id, decision, edited_text, role, plan=None):
        if decision not in FACTOR:
            raise ValueError("decision must be accept|edit|reject")
        self.store.add_feedback(plan_id, item_id, intervention_id, decision, edited_text, role)
        res = {"weight_updated": False, "router_updated": False}
        if role not in LEARNING_ROLES:
            return {**res, "reason": "role not used for learning"}
        if plan is not None and (not all(c["pass"] for c in plan["policy_checks"]) or not plan["bias_audit"]["pass"]):
            return {**res, "reason": "policy/bias check failed: flagged for review, model unchanged"}
        if not intervention_id.startswith("SYN:"):
            lo, hi = config.FEEDBACK_CLAMP
            old = self.store.weights().get(intervention_id, 1.0)
            new = round(min(hi, max(lo, old * FACTOR[decision])), 4)
            self.store.set_weight(intervention_id, new)
            res.update(weight_updated=True, old=old, new=new)
        agent = item_id.split(":")[0]
        if plan is not None and agent in router.PRIORS and decision in LABEL and plan.get("router_features"):
            x, y = plan["router_features"], LABEL[decision]
            self.store.add_replay(agent, x, y)
            W = router.get_weights(self.store)
            router.sgd_update(W, agent, x, y)
            self.store.set_router(agent, W[agent])
            res["router_updated"] = True
            if self.store.replay_size() % REPLAY_EVERY == 0:
                for a, xr, yr in self.store.sample_replay(REPLAY_BATCH):
                    W = router.get_weights(self.store)
                    router.sgd_update(W, a, xr, yr, eta=0.1)
                    self.store.set_router(a, W[a])
                res["replayed"] = REPLAY_BATCH
        return res
