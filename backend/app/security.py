import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError


_password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, ValueError):
        return False


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_flag(flag: str) -> str:
    return hashlib.sha256(flag.strip().encode("utf-8")).hexdigest()


def derive_terminal_password(team_id: str) -> str:
    from .config import settings

    master = settings.terminal_ssh_password or settings.session_secret
    if not master:
        raise RuntimeError("terminal password master secret is not configured")
    return hmac.new(master.encode(), f"terminal:{team_id}".encode(), hashlib.sha256).hexdigest()[:24]


def generate_flag(secret: str, match_id: str, round_id: str, team_id: str, service_id: str) -> str:
    if not secret:
        raise RuntimeError("FLAG_HMAC_SECRET is not configured")
    import base64

    payload = "|".join((match_id, round_id, team_id, service_id)).encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).digest()
    encoded = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")[:32]
    return f"flag{{{encoded}}}"
