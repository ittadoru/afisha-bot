import asyncio
import hashlib
import hmac
import secrets
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

SESSION_LIFETIME = timedelta(hours=8)
IDLE_LIFETIME = timedelta(minutes=30)
LOGIN_BLOCK = timedelta(minutes=15)
BOOTSTRAP_TTL_SECONDS = 300
MAX_FAILURES = 5
PASSWORD_HASHER = PasswordHasher(time_cost=2, memory_cost=19 * 1024, parallelism=1)


class AdminAuthUnavailable(RuntimeError):
    pass


class AdminAuthDenied(ValueError):
    pass


class AdminAuthBlocked(AdminAuthDenied):
    pass


@dataclass(frozen=True, slots=True)
class StaffIdentity:
    id: UUID
    login: str
    role: str


@dataclass(frozen=True, slots=True)
class StaffSession:
    identity: StaffIdentity
    token: str
    csrf_token: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class DashboardCounts:
    active_users: int
    upcoming_events: int
    pending_events: int
    open_profile_reports: int
    active_moderators: int


def contextual_hash(secret: bytes, context: str, value: str) -> bytes:
    return hmac.new(secret, f"{context}\0{value}".encode(), hashlib.sha256).digest()


async def bootstrap_first_admin(
    engine: AsyncEngine,
    *,
    login: str | None,
    password: str | None,
) -> None:
    async with engine.begin() as connection:
        await connection.execute(text("SELECT pg_advisory_xact_lock(180618)"))
        count = await connection.scalar(
            text("SELECT count(*) FROM trust_safety.staff_accounts")
        )
        if count:
            return
        normalized_login = "" if login is None else login.strip()
        if (
            not normalized_login
            or password is None
            or not password
            or len(password) > 256
        ):
            raise AdminAuthUnavailable("first admin credentials are not configured")
        password_hash = await asyncio.to_thread(PASSWORD_HASHER.hash, password)
        staff_id = uuid4()
        await connection.execute(
            text(
                """
                INSERT INTO trust_safety.staff_accounts (id, login, role)
                VALUES (:id, :login, 'admin')
                """
            ),
            {"id": staff_id, "login": normalized_login},
        )
        await connection.execute(
            text(
                """
                INSERT INTO trust_safety.staff_credentials (staff_id, password_hash)
                VALUES (:staff_id, :password_hash)
                """
            ),
            {"staff_id": staff_id, "password_hash": password_hash},
        )
        await _write_audit(
            connection,
            actor_staff_id=staff_id,
            action="staff.bootstrap",
            result="success",
        )


async def create_login_bootstrap(
    redis: Redis,
    *,
    origin: str,
    auth_secret: bytes,
) -> tuple[str, str]:
    cookie = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)
    key = "admin:bootstrap:" + contextual_hash(
        auth_secret, "admin-bootstrap-cookie", cookie
    ).hex()
    value = contextual_hash(
        auth_secret, "admin-bootstrap-binding", f"{csrf_token}\n{origin}"
    ).hex()
    try:
        stored = await redis.set(key, value, ex=BOOTSTRAP_TTL_SECONDS, nx=True)
    except Exception as error:
        raise AdminAuthUnavailable from error
    if not stored:
        raise AdminAuthUnavailable
    return cookie, csrf_token


async def consume_login_bootstrap(
    redis: Redis,
    *,
    cookie: str,
    csrf_token: str,
    origin: str,
    auth_secret: bytes,
) -> None:
    key = "admin:bootstrap:" + contextual_hash(
        auth_secret, "admin-bootstrap-cookie", cookie
    ).hex()
    expected = contextual_hash(
        auth_secret, "admin-bootstrap-binding", f"{csrf_token}\n{origin}"
    ).hex()
    script = """
        local value = redis.call('GET', KEYS[1])
        if not value or value ~= ARGV[1] then return 0 end
        redis.call('DEL', KEYS[1])
        return 1
    """
    try:
        consumed = await redis.eval(script, 1, key, expected)
    except Exception as error:
        raise AdminAuthUnavailable from error
    if consumed != 1:
        raise AdminAuthDenied("invalid bootstrap")


async def authenticate_staff(
    engine: AsyncEngine,
    *,
    login: str,
    password: str,
    source: str,
    auth_secret: bytes,
) -> StaffSession:
    normalized_login = login.strip().casefold()
    login_digest = contextual_hash(auth_secret, "admin-login", normalized_login)
    source_digest = contextual_hash(auth_secret, "admin-source", source)
    token = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)
    now = datetime.now(UTC)

    denial: AdminAuthDenied | None = None
    issued: StaffSession | None = None
    async with engine.begin() as connection:
        await connection.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
            {"key": f"{login_digest.hex()}:{source_digest.hex()}"},
        )
        limit = (
            await connection.execute(
                text(
                    """
                    SELECT failed_attempts, first_failed_at, blocked_until
                    FROM trust_safety.staff_login_limits
                    WHERE login_digest = :login_digest
                      AND source_digest = :source_digest
                    FOR UPDATE
                    """
                ),
                {"login_digest": login_digest, "source_digest": source_digest},
            )
        ).mappings().one_or_none()
        if limit is not None and limit["blocked_until"] is not None:
            if limit["blocked_until"] > now:
                await _write_audit(
                    connection,
                    actor_staff_id=None,
                    action="staff.login",
                    result="blocked",
                    source_digest=source_digest,
                )
                denial = AdminAuthBlocked("login temporarily blocked")

        if denial is None:
            row = (
                await connection.execute(
                    text(
                        """
                        SELECT a.id, a.login, a.role, c.password_hash
                        FROM trust_safety.staff_accounts AS a
                        JOIN trust_safety.staff_credentials AS c ON c.staff_id = a.id
                        WHERE lower(a.login) = :login AND a.status = 'active'
                        """
                    ),
                    {"login": normalized_login},
                )
            ).mappings().one_or_none()
            password_valid = await _password_matches(row, password)
            if row is None or not password_valid:
                await _record_failure(
                    connection,
                    login_digest=login_digest,
                    source_digest=source_digest,
                    previous=limit,
                    now=now,
                )
                await _write_audit(
                    connection,
                    actor_staff_id=None,
                    action="staff.login",
                    result="failure",
                    source_digest=source_digest,
                )
                denial = AdminAuthDenied("invalid credentials")
            else:
                await connection.execute(
                    text(
                        """
                        DELETE FROM trust_safety.staff_login_limits
                        WHERE login_digest = :login_digest
                          AND source_digest = :source_digest
                        """
                    ),
                    {"login_digest": login_digest, "source_digest": source_digest},
                )
                staff_id = row["id"]
                expires_at = now + SESSION_LIFETIME
                await connection.execute(
                    text(
                        """
                        INSERT INTO trust_safety.staff_sessions
                            (id, staff_id, token_hash, csrf_token_hash,
                             expires_at, last_seen_at)
                        VALUES (:id, :staff_id, :token_hash, :csrf_hash,
                                :expires_at, :now)
                        """
                    ),
                    {
                        "id": uuid4(),
                        "staff_id": staff_id,
                        "token_hash": contextual_hash(
                            auth_secret, "admin-session", token
                        ),
                        "csrf_hash": contextual_hash(
                            auth_secret, "admin-csrf", csrf_token
                        ),
                        "expires_at": expires_at,
                        "now": now,
                    },
                )
                await _write_audit(
                    connection,
                    actor_staff_id=staff_id,
                    action="staff.login",
                    result="success",
                    source_digest=source_digest,
                )
                issued = StaffSession(
                    identity=StaffIdentity(staff_id, row["login"], row["role"]),
                    token=token,
                    csrf_token=csrf_token,
                    expires_at=expires_at,
                )
    if denial is not None:
        raise denial
    if issued is None:
        raise AdminAuthUnavailable
    return issued


async def load_staff_session(
    engine: AsyncEngine,
    *,
    token: str,
    auth_secret: bytes,
) -> tuple[StaffIdentity, str] | None:
    now = datetime.now(UTC)
    csrf_token = secrets.token_urlsafe(32)
    async with engine.begin() as connection:
        row = (
            await connection.execute(
                text(
                    """
                    UPDATE trust_safety.staff_sessions AS s
                    SET last_seen_at = :now, csrf_token_hash = :csrf_hash
                    FROM trust_safety.staff_accounts AS a
                    WHERE s.staff_id = a.id
                      AND s.token_hash = :token_hash
                      AND s.revoked_at IS NULL
                      AND s.expires_at > :now
                      AND s.last_seen_at > :idle_cutoff
                      AND a.status = 'active'
                    RETURNING a.id, a.login, a.role
                    """
                ),
                {
                    "now": now,
                    "idle_cutoff": now - IDLE_LIFETIME,
                    "token_hash": contextual_hash(auth_secret, "admin-session", token),
                    "csrf_hash": contextual_hash(auth_secret, "admin-csrf", csrf_token),
                },
            )
        ).mappings().one_or_none()
    if row is None:
        return None
    return StaffIdentity(row["id"], row["login"], row["role"]), csrf_token


async def revoke_staff_session(
    engine: AsyncEngine,
    *,
    token: str,
    csrf_token: str,
    auth_secret: bytes,
) -> bool:
    async with engine.begin() as connection:
        staff_id = await connection.scalar(
            text(
                """
                UPDATE trust_safety.staff_sessions
                SET revoked_at = now()
                WHERE token_hash = :token_hash
                  AND csrf_token_hash = :csrf_hash
                  AND revoked_at IS NULL
                  AND expires_at > now()
                  AND last_seen_at > now() - interval '30 minutes'
                RETURNING staff_id
                """
            ),
            {
                "token_hash": contextual_hash(auth_secret, "admin-session", token),
                "csrf_hash": contextual_hash(auth_secret, "admin-csrf", csrf_token),
            },
        )
        if staff_id is None:
            return False
        await _write_audit(
            connection,
            actor_staff_id=staff_id,
            action="staff.logout",
            result="success",
        )
    return True


async def dashboard_counts(engine: AsyncEngine) -> DashboardCounts:
    async with engine.connect() as connection:
        row = (
            await connection.execute(
                text(
                    """
                    SELECT
                      (SELECT count(*) FROM accounts.users
                       WHERE status = 'active') AS active_users,
                      (SELECT count(*) FROM events.events e
                         JOIN events.event_revisions r ON r.id = e.approved_revision_id
                       WHERE e.lifecycle_status = 'published'
                         AND r.ends_at > now()) AS upcoming_events,
                      (SELECT count(*) FROM trust_safety.event_reviews
                       WHERE status = 'pending') AS pending_events,
                      (SELECT count(*) FROM trust_safety.profile_reports
                       WHERE status IN ('pending', 'reviewed')) AS open_profile_reports,
                      (SELECT count(*)
                       FROM trust_safety.staff_accounts
                       WHERE role = 'moderator'
                         AND status = 'active') AS active_moderators
                    """
                )
            )
        ).mappings().one()
    return DashboardCounts(
        active_users=row["active_users"],
        upcoming_events=row["upcoming_events"],
        pending_events=row["pending_events"],
        open_profile_reports=row["open_profile_reports"],
        active_moderators=row["active_moderators"],
    )


async def audit_page(
    engine: AsyncEngine,
    *,
    before: datetime | None,
) -> list[dict[str, object]]:
    async with engine.connect() as connection:
        rows = (
            await connection.execute(
                text(
                    """
                    SELECT l.id, l.created_at, a.login AS actor, l.action, l.result
                    FROM trust_safety.staff_audit_log AS l
                    LEFT JOIN trust_safety.staff_accounts AS a
                      ON a.id = l.actor_staff_id
                    WHERE (CAST(:before AS timestamptz) IS NULL
                       OR l.created_at < CAST(:before AS timestamptz))
                    ORDER BY l.created_at DESC, l.id DESC
                    LIMIT 50
                    """
                ),
                {"before": before},
            )
        ).mappings().all()
    return [dict(row) for row in rows]


async def record_admin_event(
    engine: AsyncEngine,
    *,
    action: str,
    result: str,
    actor_staff_id: UUID | None = None,
    source_digest: bytes | None = None,
) -> None:
    async with engine.begin() as connection:
        await _write_audit(
            connection,
            actor_staff_id=actor_staff_id,
            action=action,
            result=result,
            source_digest=source_digest,
        )


async def _password_matches(
    row: Mapping[str, Any] | None,
    password: str,
) -> bool:
    if row is not None and 0 < len(password) <= 256:
        try:
            return bool(
                await asyncio.to_thread(
                    PASSWORD_HASHER.verify, row["password_hash"], password
                )
            )
        except (InvalidHashError, VerificationError):
            return False
    # Keep an unknown login materially as expensive as a known one.
    dummy_hash = await asyncio.to_thread(
        PASSWORD_HASHER.hash, secrets.token_urlsafe(24)
    )
    try:
        await asyncio.to_thread(PASSWORD_HASHER.verify, dummy_hash, password[:256])
    except VerificationError:
        pass
    return False


async def _record_failure(
    connection: AsyncConnection,
    *,
    login_digest: bytes,
    source_digest: bytes,
    previous: Mapping[str, Any] | None,
    now: datetime,
) -> None:
    reset = previous is None or previous["first_failed_at"] < now - LOGIN_BLOCK
    attempts = 1 if reset else int(previous["failed_attempts"]) + 1
    first_failed_at = now if reset else previous["first_failed_at"]
    blocked_until = now + LOGIN_BLOCK if attempts >= MAX_FAILURES else None
    await connection.execute(
        text(
            """
            INSERT INTO trust_safety.staff_login_limits
                (login_digest, source_digest, failed_attempts, first_failed_at,
                 blocked_until, updated_at)
            VALUES (:login_digest, :source_digest, :attempts, :first_failed_at,
                    :blocked_until, :now)
            ON CONFLICT (login_digest, source_digest) DO UPDATE SET
                failed_attempts = EXCLUDED.failed_attempts,
                first_failed_at = EXCLUDED.first_failed_at,
                blocked_until = EXCLUDED.blocked_until,
                updated_at = EXCLUDED.updated_at
            """
        ),
        {
            "login_digest": login_digest,
            "source_digest": source_digest,
            "attempts": attempts,
            "first_failed_at": first_failed_at,
            "blocked_until": blocked_until,
            "now": now,
        },
    )


async def _write_audit(
    connection: AsyncConnection,
    *,
    actor_staff_id: UUID | None,
    action: str,
    result: str,
    source_digest: bytes | None = None,
) -> None:
    await connection.execute(
        text(
            """
            INSERT INTO trust_safety.staff_audit_log
                (id, actor_staff_id, action, result, source_digest)
            VALUES (:id, :actor_staff_id, :action, :result, :source_digest)
            """
        ),
        {
            "id": uuid4(),
            "actor_staff_id": actor_staff_id,
            "action": action,
            "result": result,
            "source_digest": source_digest,
        },
    )
