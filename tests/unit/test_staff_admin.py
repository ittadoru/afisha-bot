from afishabot.modules.trust_safety.application.staff_admin import (
    PASSWORD_HASHER,
    contextual_hash,
)


def test_staff_secrets_use_separate_hash_contexts() -> None:
    secret = b"test-secret-that-is-at-least-thirty-two-bytes"

    assert contextual_hash(secret, "admin-session", "same-value") != contextual_hash(
        secret,
        "admin-csrf",
        "same-value",
    )


def test_admin_password_hasher_uses_owasp_mvp_parameters() -> None:
    assert PASSWORD_HASHER.memory_cost == 19 * 1024
    assert PASSWORD_HASHER.time_cost == 2
    assert PASSWORD_HASHER.parallelism == 1
