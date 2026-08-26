import bcrypt

from app.core.security import PASSWORD_HASH_PREFIX, hash_password, verify_password


def test_password_hash_round_trip_uses_bcrypt_sha256() -> None:
    password_hash = hash_password("correct horse battery staple")

    assert password_hash.startswith(PASSWORD_HASH_PREFIX)
    assert verify_password("correct horse battery staple", password_hash) is True
    assert verify_password("wrong password", password_hash) is False


def test_password_hash_supports_more_than_72_utf8_bytes() -> None:
    password = "длинный-пароль-" * 12

    assert verify_password(password, hash_password(password)) is True


def test_legacy_passlib_bcrypt_hashes_remain_valid() -> None:
    password = "legacy-password"
    legacy_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")

    assert verify_password(password, legacy_hash) is True
    assert verify_password("wrong password", legacy_hash) is False


def test_malformed_password_hash_is_rejected() -> None:
    assert verify_password("password", "not-a-bcrypt-hash") is False
