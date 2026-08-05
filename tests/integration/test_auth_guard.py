import os
import secrets

import pytest
from redis.asyncio import Redis

from afishabot.modules.accounts.infrastructure.auth_guard import (
    AuthGuardDenied,
    create_bootstrap,
    consume_bootstrap_and_claim_payload,
)

pytestmark = pytest.mark.integration
AUTH_SECRET = b"integration-auth-secret-that-is-long-enough"


def required_redis_url() -> str:
    value = os.environ.get("AFISHA_REDIS_URL")
    if value is None:
        pytest.skip("AFISHA_REDIS_URL is provided only by the VPS gate")
    return value


async def test_bootstrap_and_init_data_are_consumed_once() -> None:
    redis = Redis.from_url(required_redis_url(), decode_responses=True)
    marker = secrets.token_hex(12)
    try:
        proof = await create_bootstrap(
            redis,
            origin="https://podvval.xyz",
            request_fingerprint=marker,
            auth_secret=AUTH_SECRET,
        )
        await consume_bootstrap_and_claim_payload(
            redis,
            nonce=proof.nonce,
            cookie=proof.cookie,
            origin="https://podvval.xyz",
            payload_digest=marker,
            auth_secret=AUTH_SECRET,
        )
        with pytest.raises(AuthGuardDenied):
            await consume_bootstrap_and_claim_payload(
                redis,
                nonce=proof.nonce,
                cookie=proof.cookie,
                origin="https://podvval.xyz",
                payload_digest=marker,
                auth_secret=AUTH_SECRET,
            )
    finally:
        await redis.aclose()
