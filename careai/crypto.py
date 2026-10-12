"""Field-level encryption at rest (Fernet / AES-128-CBC + HMAC). Key from CAREAI_FERNET_KEY.
In production (CAREAI_ENV=production) the key is mandatory. In dev a key file is generated (git-ignored)."""
import os
from cryptography.fernet import Fernet
from . import config

_f = None


def _key():
    k = os.getenv("CAREAI_FERNET_KEY")
    if k:
        return k.encode()
    if os.getenv("CAREAI_ENV") == "production":
        raise RuntimeError("CAREAI_FERNET_KEY is required in production (generate: python -m careai.cli genkey)")
    kp = config.DATA_DIR / ".devkey"
    if not kp.exists():
        kp.write_bytes(Fernet.generate_key()); os.chmod(kp, 0o600)
    return kp.read_bytes()


def f():
    global _f
    if _f is None:
        _f = Fernet(_key())
    return _f


def enc(s: str) -> str:
    return f().encrypt(s.encode()).decode()


def dec(s: str) -> str:
    return f().decrypt(s.encode()).decode()
