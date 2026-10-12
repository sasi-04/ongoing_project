# CARE-AI (MVP backend)
Adaptive neuro-symbolic multi-agent decision support for personalised neurodevelopmental education plans.
**Decision support only. Not a medical device. Every plan is a draft that requires human approval.**

## One-Click Company Presentation Launcher
```bash
# Windows instant launch:
run_demo.bat

# Or run via Python:
python run_demo.py
```
This automatically verifies keys, prepares the SQLite database, launches the Uvicorn server, and opens `http://localhost:8000/`.  
See [`docs/COMPANY_PRESENTATION.md`](file:///d:/s5/careai/docs/COMPANY_PRESENTATION.md) for the word-for-word executive pitch script, live demo walkthrough, and Q&A defense.

## Standard Setup & Testing
```bash
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q                              # 22 tests (15 core + 7 clinical pillars)
python -m eval.run_eval data/synthetic_cases.json test
uvicorn careai.api:app                           # dashboard: http://localhost:8000/   API docs: /docs
```

## 7 Production Clinical Intelligence Pillars
1. **Interactive Executive Presentation Deck:** 6 full presentation slides built directly into the UI with arrow key navigation, KPI metrics, architecture flow, and live scenario launching.
2. **Clinical AI Consultation Copilot:** Real-time conversational intelligence with semantic literature citations, diagnostic concept entity tags, suggestion chips, and responsive drawer (`POST /clinical/chat`).
3. **Patient Vitals & Biometric Telemetry Tracker:** Longitudinal persistence (`vitals` SQLite table), ACC/AHA risk categorization, SVG timeline trend charts, and manual intake logging (`GET/POST /patients/{id}/vitals`).
4. **Multimodal Vision & Speech Intake Lab:** Real-time visual-motor/ocular strain and acoustic prosody/speech biomarker analysis using OpenCV and MediaPipe (`POST /multimodal/vision-scan`, `POST /multimodal/audio-scan`).
5. **Comprehensive Clinical Dossier & PDF Export:** Printable/exportable clinical reports (`/plans/{pid}/export`) with multi-agent consensus breakdown, digital twin prognosis, and SHA-256 cryptographic audit seal.
6. **Patient Voice AI Assistant:** Spoken conversational assistant with Web Speech ASR & TTS, voice vitals logging, and acute emergency triage screening (`POST /clinical/voice-command`).
7. **Automated Clinical SOAP Note Generator:** Formal Subjective, Objective, Assessment, and Plan encounter documentation with automated ICD-10-CM diagnostic and CPT billing codes (`/clinical/soap-notes`).

## Pipeline (matches Section 5.2.2 of the plan)
intake + de-identification -> **Adaptive Agent Selection** (router) -> parallel analysis agents (medical, academic,
behavior, speech, vision) each calling **Adaptive Hybrid RAG** (difficulty estimate -> depth/source choice -> vector + KG
traversal + rules, multi-pass) -> **Consensus** (dedupe, conflict detection, weighted debate, synthesis) -> **Planning**
(draft IEP + **Digital Twin** what-if) -> **Risk** -> **Explainability** -> **Policy/Bias** -> **Parent Communication** -> human review (HITL) -> **Feedback Learning** (bounded retrieval re-weighting).

## Agents (12, not 11 as the abstract says; the spec lists 12)
medical, academic, behavior, speech, vision (`agents/analysis.py`), planning, consensus, explainability, risk,
feedback learning, parent communication, policy compliance.

## API (JWT bearer auth; roles and caseloads come from the user record)
`POST /auth/login` | `POST /auth/register` | `POST /auth/change-password` | `PUT /auth/profile` | `GET /auth/me` |
`POST /cases` | `GET /plans`, `/plans/{id}` (parents: goals + summary only, only their children) |
`GET /plans/{id}/decisions` | `POST /plans/{id}/review` | `POST /plans/{id}/approve` (teacher/clinician; every item decided; policy+bias pass) |
`GET /plans/{id}/audit`, `/audit/verify` (hash chain) | `GET /plans/{pid}/export` (printable clinical dossier) |
`GET /patients/{id}/vitals`, `POST /patients/{id}/vitals` (biometric telemetry) |
`POST /clinical/chat` (clinical consultation copilot) |
`POST /multimodal/vision-scan`, `POST /multimodal/audio-scan` (computer vision & acoustic intake) |
`GET /feedback/stats` | `GET /literature/search`, `/literature/papers` | `POST /admin/users`, `GET /admin/users-list`.

## Security measures implemented
PBKDF2-SHA256 (310k) passwords; JWT with expiry; login throttling (5 failed attempts window); role + caseload authorization; Fernet encryption of cases/plans at rest;
tamper-evident hash-chained audit log; strict CSP/security headers; request-size limit; non-root Docker; secrets only via env in production.
NOT included (do these before real data): TLS termination, key rotation/KMS, backups, rate limiting at the proxy, SSO/MFA, DPIA/consent and legal review (e.g. India's DPDP Act, and local child-data rules).

## Honest status
| Area | Status |
|---|---|
| Orchestration, logistic router, adaptive RAG (Eq.2-4), KG, rules, consensus, planning, HITL, audit, learning loop (Alg.4), policy + counterfactual bias test, auth, encryption, dashboard | Working, tested (20 tests + jsdom UI flow) |
| Research library | 1,171 passages from the 13 PDFs with page citations. Papers are design references, NOT clinical evidence for interventions |
| Knowledge base | **22 illustrative seed interventions**, no real citations. Needs clinician/educator curation |
| Digital twin, risk model | Transparent but **uncalibrated priors** |
| Speech / Vision agents | Multimodal CV (OpenCV/MediaPipe) & acoustic prosody biomarker extraction operational; text notes integrated |
| Dense embeddings | Code complete; tested only with the TF-IDF fallback (no Ollama in the build sandbox) |
| LLM paths | Never exercised in the build sandbox (no Ollama); templates and rule-based clinical intelligence tested |
| Evaluation data | Placeholder labels; "targets MET" is meaningless until real expert-authored plans are used |
| Dashboard | Verified with jsdom against the live server; Obsidian Black & Cobalt Blue design system with live copilot drawer, vitals timeline, and multimodal intake lab |

See `docs/VERIFICATION.md` for the plan/paper/code cross-check and the paper's citation issues.
