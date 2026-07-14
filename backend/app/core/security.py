import base64
import hashlib
import hmac
import json
import os
import time
from datetime import timedelta

from app.core.config import get_settings


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 210_000)
    return f"pbkdf2_sha256$210000${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, rounds, salt, expected = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), base64.urlsafe_b64decode(salt), int(rounds)
        )
        return hmac.compare_digest(base64.urlsafe_b64encode(digest).decode(), expected)
    except (ValueError, TypeError):
        return False


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def create_access_token(subject: str, role: str) -> str:
    settings = get_settings()
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    expires = int(time.time() + timedelta(minutes=settings.access_token_minutes).total_seconds())
    payload = _b64(json.dumps({"sub": subject, "role": role, "exp": expires}).encode())
    signature = _b64(hmac.new(settings.secret_key.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest())
    return f"{header}.{payload}.{signature}"


def decode_access_token(token: str) -> dict:
    header, payload, signature = token.split(".")
    expected = _b64(hmac.new(get_settings().secret_key.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(signature, expected):
        raise ValueError("invalid signature")
    padded = payload + "=" * (-len(payload) % 4)
    data = json.loads(base64.urlsafe_b64decode(padded))
    if data["exp"] < time.time():
        raise ValueError("token expired")
    return data

