"""python -m careai.cli genkey | create-user <username> <role> [student_id,...]"""
import getpass, sys
from cryptography.fernet import Fernet
from . import auth
from .store import Store


def main(a):
    if a[:1] == ["genkey"]:
        print("CAREAI_FERNET_KEY=" + Fernet.generate_key().decode())
        import secrets; print("CAREAI_JWT_SECRET=" + secrets.token_hex(32))
    elif a[:1] == ["create-user"] and len(a) >= 3:
        role = a[2]
        assert role in auth.ROLES, f"role must be one of {sorted(auth.ROLES)}"
        pw = getpass.getpass("Password (min 10 chars): ")
        Store().add_user(a[1], auth.hash_password(pw), role, a[3].split(",") if len(a) > 3 else [])
        print("created", a[1], role)
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
