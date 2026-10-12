# Verification report

## A. Plan document (main_idea.docx) vs paper (main.pdf) vs code
| Item | Finding | Resolution |
|---|---|---|
| Agent count | docx abstract/§5.2 say "eleven" but list 12; paper says "twelve" | 12 implemented. Fix "eleven" in the docx |
| docx truncated at §7.1 | Pipeline/tech-stack/evaluation sections not received | Pipeline taken from §5.2.2 + paper §IV-VI |
| Router | Paper Eq.1 is logistic a_i = sigma(w.x+b), threshold tau, fallback to Planning | Implemented (`agents/router.py`), learned via Alg. 4 |
| Retrieval depth | Paper Eq.2-3: d = 1 - max sim, k* = kmin + ceil((kmax-kmin)d) | Implemented, kmin=3, kmax=10 (`knowledge/retrieval.py`) |
| Fusion | Paper Eq.4 weighted sum of vector/KG/rule | Implemented, weights in `config.py` |
| Consensus | Paper Eq.5 confidence-weighted vote | Implemented; two documented EXTENSIONS: expertise weights and synthesis for close votes |
| Confidence | Paper Eq.6 mean absolute Shapley value | Implemented as exact Shapley of the additive fusion model (`confidence_shapley_eq6`); the displayed `confidence` is the fused score |
| Risk | Paper Eq.7 logistic | Implemented, UNCALIBRATED priors |
| Continual learning | Paper Alg.4: replay buffer, gradient step, policy-fail => unchanged | Implemented (`agents/feedback.py`) |
| Metrics | Precision/recall/F1/agreement, per condition, held-out test | `eval/run_eval.py` (with deterministic split); needs real data |

## B. Numeric claims in the paper vs source PDFs
| Claim in paper | Source says | Status |
|---|---|---|
| 92.4% recommendation accuracy [1] | Student Agent Top-1 accuracy 92.4 | OK |
| 93.6% EEG ASD classification [7] | SVM-RBF 93.59% | OK (rounded) |
| 91-93% ASD screening [9] | "accuracy of 91% - 93%" | OK |
| >95% retrieval accuracy [12] | "exceeds 95%" only in some categories (Environmental Sciences, Politics...); History lower | REWORD: "in some categories" |
| 95.1% tutoring QA [13] | 95.12% multiple-choice (91.7% open-ended) in the floodplain-certification tool | OK number; relabel as "multiple-choice QA accuracy", not "tutoring" |
| 78.6% user satisfaction [5] | 78.57% of students agreed an item aligned with course objectives | REWORD: not strictly "satisfaction" |
| 82% satisfaction [10] | A study reviewed inside [10] (adaptive AI robot) reports 82% | CITE as secondary source |
| Contribution (4) cites [11] for "transparency gap in assistive AI" | That claim belongs to [6] (Accessible XAI) | FIX citation |

## C. Limits (also in README)
Knowledge base is illustrative seed content; twin/risk priors are uncalibrated; speech/vision are text-only;
the bundled evaluation data are placeholder labels; the papers are design references, not clinical efficacy evidence.
