"""Authentication: PBKDF2 password hashing, JWT (HS256) access tokens, login throttling.
Roles come from the user record, never from client-supplied headers."""
import hashlib, hmac, os, secrets, time
import jwt
from . import config

ALGO, TTL = "HS256", int(os.getenv("CAREAI_TOKEN_TTL_S", 8 * 3600))
ROLES = {"teacher", "clinician", "therapist", "parent", "patient", "admin"}
_FAILS: dict = {}
MAX_FAILS, WINDOW = int(os.getenv("CAREAI_MAX_LOGIN_FAILS", 5)), 900


def _secret():
    s = os.getenv("CAREAI_JWT_SECRET")
    if s:
        return s
    if os.getenv("CAREAI_ENV") == "production":
        raise RuntimeError("CAREAI_JWT_SECRET is required in production")
    kp = config.DATA_DIR / ".jwtsecret"
    if not kp.exists():
        kp.write_text(secrets.token_hex(32)); os.chmod(kp, 0o600)
    return kp.read_text()


def hash_password(pw: str, salt: bytes = None) -> str:
    if len(pw) < 6:
        raise ValueError("password must be at least 6 characters")
    salt = salt or os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, 310_000)
    return salt.hex() + "$" + dk.hex()


def verify_password(pw: str, stored: str) -> bool:
    salt_hex, _ = stored.split("$")
    return hmac.compare_digest(hash_password(pw, bytes.fromhex(salt_hex)), stored)


def throttled(key: str) -> bool:
    now = time.time()
    _FAILS[key] = [t for t in _FAILS.get(key, []) if now - t < WINDOW]
    return len(_FAILS[key]) >= MAX_FAILS


def record_fail(key: str):
    _FAILS.setdefault(key, []).append(time.time())


def make_token(username: str, role: str) -> str:
    now = int(time.time())
    return jwt.encode({"sub": username, "role": role, "iat": now, "exp": now + TTL}, _secret(), algorithm=ALGO)


def read_token(tok: str) -> dict:
    return jwt.decode(tok, _secret(), algorithms=[ALGO])
