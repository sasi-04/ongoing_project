"""One-click demonstration launcher for CARE AI.
Initializes keys, verifies database, starts Uvicorn server, and opens default browser.
"""
import os
import sys
import time
import webbrowser
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)

# Set defaults if not present
os.environ.setdefault("CAREAI_LLM", "off")
os.environ.setdefault("CAREAI_EMBED", "auto")
os.environ.setdefault("CAREAI_BOOTSTRAP_ADMIN_PASSWORD", "admin12345")

print("=" * 68)
print("  CARE AI · Patient Clinical Intelligence Platform")
print("  Interactive Executive Presentation & Live Demo Launcher")
print("=" * 68)

# Check keys
data_dir = ROOT / "data"
data_dir.mkdir(parents=True, exist_ok=True)

devkey = data_dir / ".devkey"
if not devkey.exists() and "CAREAI_FERNET_KEY" not in os.environ:
    from cryptography.fernet import Fernet
    k = Fernet.generate_key().decode()
    devkey.write_text(k)
    print("✓ Generated temporary Fernet key for presentation session.")

jwtsecret = data_dir / ".jwtsecret"
if not jwtsecret.exists() and "CAREAI_JWT_SECRET" not in os.environ:
    import secrets
    s = secrets.token_hex(32)
    jwtsecret.write_text(s)
    print("✓ Generated temporary JWT secret for presentation session.")

print("\n[Credentials for Company Presentation]")
print("  • Clinician (Dr. Sarah Vance) : clinician / clinician123")
print("  • Patient (John Doe)          : patient   / patient123")
print("  • Advocate / Caregiver        : parent    / parent123")
print("  • System Administrator        : admin     / admin12345")
print("\n[Features Ready for Presentation]")
print("  1. Executive Presentation Deck: Built into top bar & sidebar")
print("  2. Clinical AI Copilot & Voice Assistant (Web Speech + Emergency Triage)")
print("  3. Longitudinal Biometric Vitals Telemetry Tracker")
print("  4. Multimodal Vision & Speech Lab (OpenCV + MediaPipe)")
print("  5. Automated Clinical SOAP Notes with ICD-10 & CPT Billing Codes")
print("  6. Exportable Printable Clinical Dossiers with SHA-256 Audit Seal")
print("\nStarting local server at http://localhost:8000 ...")

def open_browser():
    time.sleep(1.8)
    print("✓ Opening web browser to http://localhost:8000/ ...")
    webbrowser.open("http://localhost:8000/")

import threading
threading.Thread(target=open_browser, daemon=True).start()

try:
    import uvicorn
    uvicorn.run("careai.api:app", host="127.0.0.1", port=8000, reload=False, log_level="info")
except KeyboardInterrupt:
    print("\nCARE AI demonstration server stopped.")
