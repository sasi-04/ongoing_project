import os, tempfile, pathlib
os.environ["CAREAI_LLM"] = "off"
db_path = str(pathlib.Path(tempfile.mkdtemp()) / "pillar_test.db")
os.environ["CAREAI_DB"] = db_path

import pytest
from fastapi.testclient import TestClient
from careai.api import app

client = TestClient(app)

def get_auth_token(username="admin_user", role="admin"):
    try:
        r = client.post("/auth/register", json={"username": username, "password": "password123", "role": role})
        if r.status_code == 200:
            return {"Authorization": f"Bearer {r.json()['token']}"}
    except Exception:
        pass
    r = client.post("/auth/login", json={"username": username, "password": "password123"})
    assert r.status_code == 200, f"Login failed: {r.text}"
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_pillar1_clinical_copilot_chat():
    headers = get_auth_token("copilot_tester", "clinician")
    payload = {
        "message": "What is the recommended DASH diet protocol for elevated blood pressure?",
        "history": []
    }
    res = client.post("/clinical/chat", json=payload, headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()
    assert "reply" in data
    assert "citations" in data
    assert "suggestions" in data
    assert len(data["suggestions"]) > 0
    assert "safety_audit" in data
    assert data["safety_audit"]["guardrail"] == "HIPAA & Clinical Policy Enforced"


def test_pillar2_vitals_telemetry():
    headers = get_auth_token("vitals_tester", "clinician")
    # 1. Post new vitals record
    vital_entry = {
        "systolic": 128,
        "diastolic": 82,
        "pulse": 72,
        "sleep_hours": 7.5,
        "stress_level": 3,
        "glucose": 95.0,
        "notes": "Patient calm, baseline test"
    }
    post_res = client.post("/patients/P-101/vitals", json=vital_entry, headers=headers)
    assert post_res.status_code == 200, post_res.text
    res_data = post_res.json()
    assert res_data["status"] == "recorded"
    assert res_data["risk_flag"] in ["normal", "elevated", "stage1", "stage2"]
    assert res_data["vitals"]["student_id"] == "P-101"
    assert res_data["vitals"]["systolic"] == 128

    # 2. Get vitals history
    get_res = client.get("/patients/P-101/vitals", headers=headers)
    assert get_res.status_code == 200, get_res.text
    vitals_resp = get_res.json()
    assert "vitals" in vitals_resp
    v_list = vitals_resp["vitals"]
    assert isinstance(v_list, list)
    assert len(v_list) >= 1
    assert v_list[0]["student_id"] == "P-101"


def test_pillar3_multimodal_intake():
    headers = get_auth_token("multimodal_tester", "clinician")
    
    # 1. Vision Scan (blank 1x1 png base64)
    blank_png = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
    v_res = client.post("/multimodal/vision-scan", json={"image": blank_png}, headers=headers)
    assert v_res.status_code == 200, v_res.text
    v_data = v_res.json()
    assert "gaze_stability_score" in v_data
    assert "ocular_strain_index" in v_data
    assert "visual_attention_pct" in v_data

    # 2. Audio Scan (speech biomarker scan)
    a_res = client.post("/multimodal/audio-scan", json={
        "audio": "UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA=",
        "transcript": "Patient articulates clear speech during clinical interview."
    }, headers=headers)
    assert a_res.status_code == 200, a_res.text
    a_data = a_res.json()
    assert "speech_rate_wpm" in a_data
    assert "articulation_clarity_pct" in a_data
    assert "vocal_stress_index" in a_data


def test_pillar4_clinical_dossier_export():
    headers = get_auth_token("export_tester", "clinician")
    
    # Create a case and plan first
    case_payload = {
        "student_id": "P-202",
        "age": 16,
        "conditions": ["adhd", "dyslexia"],
        "academic": {"reading": 45, "math": 70},
        "behavior_notes": ["high distractibility", "anxiety"],
        "incidents_last_30d": 2,
        "attendance_rate": 0.95
    }
    case_res = client.post("/cases", json=case_payload, headers=headers)
    assert case_res.status_code == 200, case_res.text
    plan_id = case_res.json()["plan_id"]
    
    # Export dossier HTML
    export_res = client.get(f"/plans/{plan_id}/export", headers=headers)
    assert export_res.status_code == 200, export_res.text
    assert "text/html" in export_res.headers["content-type"]
    html_content = export_res.text
    assert "Clinical Care Dossier" in html_content
    assert plan_id in html_content
    assert "CRYPTOGRAPHIC AUDIT SEAL" in html_content
    assert "DECISION SUPPORT" in html_content


def test_pillar5_profile_and_security():
    headers = get_auth_token("sec_user", "clinician")
    
    # 1. Update Profile (caseload)
    up_res = client.put("/auth/profile", json={"students": ["P-101", "P-202", "P-303"]}, headers=headers)
    assert up_res.status_code == 200, up_res.text
    assert up_res.json()["status"] == "ok"
    assert "P-303" in up_res.json()["students"]

    # 2. Change Password
    pw_res = client.post("/auth/change-password", json={
        "old_password": "password123",
        "new_password": "new_secure_password_999"
    }, headers=headers)
    assert pw_res.status_code == 200, pw_res.text
    assert pw_res.json()["status"] == "ok"

    # 3. Verify login with new password
    new_login = client.post("/auth/login", json={"username": "sec_user", "password": "new_secure_password_999"})
    assert new_login.status_code == 200

    # 4. Verify login with old password fails
    old_login = client.post("/auth/login", json={"username": "sec_user", "password": "password123"})
    assert old_login.status_code == 401

    # 5. Admin users list (as admin)
    admin_headers = get_auth_token("admin_master", "admin")
    users_res = client.get("/admin/users-list", headers=admin_headers)
    assert users_res.status_code == 200
    users = users_res.json()["users"]
    assert any(u["username"] == "sec_user" for u in users)


def test_pillar6_patient_voice_ai_assistant():
    headers = get_auth_token("voice_patient_user", "patient")

    # 1. Voice vitals logging
    log_res = client.post("/clinical/voice-command", json={
        "transcript": "Please log my blood pressure 138 over 88 and pulse 76",
        "student_id": "P-VOICE-1"
    }, headers=headers)
    assert log_res.status_code == 200, log_res.text
    log_data = log_res.json()
    assert log_data["intent"] == "vitals_logged"
    assert log_data["is_emergency"] is False
    assert log_data["vitals_recorded"]["systolic"] == 138
    assert log_data["vitals_recorded"]["diastolic"] == 88
    assert log_data["vitals_recorded"]["pulse"] == 76
    assert "138 over 88" in log_data["speakable_text"]

    # 2. Voice vitals inquiry
    inq_res = client.post("/clinical/voice-command", json={
        "transcript": "What is my blood pressure and how are my vitals today?",
        "student_id": "P-VOICE-1"
    }, headers=headers)
    assert inq_res.status_code == 200, inq_res.text
    inq_data = inq_res.json()
    assert inq_data["intent"] == "vitals_inquiry"
    assert "138" in inq_data["speakable_text"]

    # 3. Emergency triage detection
    em_res = client.post("/clinical/voice-command", json={
        "transcript": "I am having severe chest pain and short of breath",
        "student_id": "P-VOICE-1"
    }, headers=headers)
    assert em_res.status_code == 200, em_res.text
    em_data = em_res.json()
    assert em_data["intent"] == "emergency_triage"
    assert em_data["is_emergency"] is True
    assert "911" in em_data["speakable_text"]
    assert "Emergency Alert" in em_data["speakable_text"]

    # 4. Spoken dietary / general clinical question
    diet_res = client.post("/clinical/voice-command", json={
        "transcript": "What foods are recommended on the DASH diet for blood pressure?",
        "student_id": "P-VOICE-1"
    }, headers=headers)
    assert diet_res.status_code == 200, diet_res.text
    diet_data = diet_res.json()
    assert diet_data["intent"] == "general_qa"
    assert len(diet_data["speakable_text"]) > 10
    assert "citations" in diet_data


def test_pillar7_automated_clinical_soap_note_generator():
    headers = get_auth_token("clinician_soap", "clinician")

    # 1. Generate SOAP note
    gen_res = client.post("/clinical/soap-notes/generate", json={
        "student_id": "P-SOAP-101",
        "encounter_type": "Comprehensive Ambulatory Telehealth Consultation",
        "chief_complaint": "Follow-up evaluation of morning blood pressure elevation and nocturnal sleep fragmentation."
    }, headers=headers)
    assert gen_res.status_code == 200, gen_res.text
    note = gen_res.json()
    assert "id" in note
    assert note["student_id"] == "P-SOAP-101"
    assert note["status"] == "draft"
    assert "CHIEF COMPLAINT" in note["subjective"]
    assert "VITAL SIGNS" in note["objective"]
    assert "ACC/AHA" in note["assessment"]
    assert "DASH Protocol" in note["plan"]
    assert len(note["icd10_codes"]) >= 2
    assert len(note["cpt_codes"]) >= 2
    nid = note["id"]

    # 2. List SOAP notes
    list_res = client.get("/clinical/soap-notes?student_id=P-SOAP-101", headers=headers)
    assert list_res.status_code == 200
    notes = list_res.json()["notes"]
    assert any(n["id"] == nid for n in notes)

    # 3. Sign SOAP note
    sign_res = client.post(f"/clinical/soap-notes/{nid}/sign", json={
        "clinician_name": "Dr. Sarah Vance, MD (Cardiovascular Medicine)"
    }, headers=headers)
    assert sign_res.status_code == 200, sign_res.text
    signed = sign_res.json()
    assert signed["status"] == "signed"
    assert signed["clinician"] == "Dr. Sarah Vance, MD (Cardiovascular Medicine)"
    assert len(signed["signature_hash"]) == 64

    # 4. Export SOAP HTML Dossier
    export_res = client.get(f"/clinical/soap-notes/{nid}/export", headers=headers)
    assert export_res.status_code == 200
    assert "text/html" in export_res.headers["content-type"]
    html = export_res.text
    assert "SUBJECTIVE" in html
    assert "OBJECTIVE" in html
    assert "ASSESSMENT" in html
    assert "PLAN" in html
    assert "CRYPTOGRAPHIC AUDIT SEAL" in html

