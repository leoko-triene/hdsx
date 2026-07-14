from app.core.security import create_access_token, decode_access_token, hash_password, verify_password


def test_password_roundtrip():
    encoded = hash_password("secret123")
    assert verify_password("secret123", encoded)
    assert not verify_password("wrong", encoded)


def test_token_roundtrip():
    token = create_access_token("42", "teacher")
    payload = decode_access_token(token)
    assert payload["sub"] == "42"
    assert payload["role"] == "teacher"

