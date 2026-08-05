import hashlib
import hmac
import secrets
from dataclasses import dataclass

from redis.asyncio import Redis

BOOTSTRAP_TTL_SECONDS = 300
RATE_LIMIT_SECONDS = 60
RATE_LIMIT_REQUESTS = 20


class AuthGuardUnavailable(RuntimeError):
    pass


class AuthGuardDenied(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class BootstrapProof:
    nonce: str
    cookie: str


def protected_digest(secret: bytes, value: str) -> str:
    return hmac.new(secret, value.encode(), hashlib.sha256).hexdigest()


async def create_bootstrap(
    redis: Redis,
    *,
    origin: str,
    request_fingerprint: str,
    auth_secret: bytes,
) -> BootstrapProof:
    try:
        allowed = await _within_rate_limit(redis, request_fingerprint)
        if not allowed:
            raise AuthGuardDenied("rate limit exceeded")
        nonce = secrets.token_urlsafe(32)
        cookie = secrets.token_urlsafe(32)
        key = f"auth:bootstrap:{protected_digest(auth_secret, nonce)}"
        binding = protected_digest(auth_secret, f"{cookie}\n{origin}")
        stored = await redis.set(  # pyright: ignore[reportUnknownMemberType]
            key,
            binding,
            ex=BOOTSTRAP_TTL_SECONDS,
            nx=True,
        )
    except AuthGuardDenied:
        raise
    except Exception as error:
        raise AuthGuardUnavailable from error
    if not stored:
        raise AuthGuardUnavailable
    return BootstrapProof(nonce=nonce, cookie=cookie)


async def consume_bootstrap_and_claim_payload(
    redis: Redis,
    *,
    nonce: str,
    cookie: str,
    origin: str,
    payload_digest: str,
    auth_secret: bytes,
) -> None:
    bootstrap_key = f"auth:bootstrap:{protected_digest(auth_secret, nonce)}"
    replay_key = f"auth:replay:{payload_digest}"
    expected_binding = protected_digest(auth_secret, f"{cookie}\n{origin}")
    script = """
        local binding = redis.call('GET', KEYS[1])
        if not binding or binding ~= ARGV[1] then return 0 end
        if redis.call('EXISTS', KEYS[2]) == 1 then return -1 end
        redis.call('DEL', KEYS[1])
        redis.call('SET', KEYS[2], '1', 'EX', ARGV[2], 'NX')
        return 1
    """
    try:
        result = await redis.eval(  # pyright: ignore[reportUnknownMemberType]
            script,
            2,
            bootstrap_key,
            replay_key,
            expected_binding,
            BOOTSTRAP_TTL_SECONDS,
        )
    except Exception as error:
        raise AuthGuardUnavailable from error
    if result != 1:
        raise AuthGuardDenied("bootstrap or initData is not fresh")


async def _within_rate_limit(redis: Redis, fingerprint: str) -> bool:
    key = f"auth:rate:{fingerprint}"
    count = await redis.incr(key)  # pyright: ignore[reportUnknownMemberType]
    if count == 1:
        await redis.expire(  # pyright: ignore[reportUnknownMemberType]
            key,
            RATE_LIMIT_SECONDS,
        )
    return bool(count <= RATE_LIMIT_REQUESTS)
