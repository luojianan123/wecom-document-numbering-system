import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AuthState


class AuthStateError(ValueError):
    pass


def _hash_state(state: str) -> str:
    return hashlib.sha256(state.encode("utf-8")).hexdigest()


def _safe_return_path(value: str) -> str:
    if not value.startswith("/") or value.startswith("//"):
        return "/"
    return value[:512]


def issue_auth_state(
    db: Session,
    purpose: str,
    return_path: str,
    lifetime_minutes: int = 10,
) -> str:
    state = secrets.token_urlsafe(32)
    record = AuthState(
        state_hash=_hash_state(state),
        purpose=purpose,
        return_path=_safe_return_path(return_path),
        expires_at=datetime.now(UTC) + timedelta(minutes=lifetime_minutes),
    )
    db.add(record)
    db.commit()
    return state


def consume_auth_state(db: Session, state: str, purpose: str) -> str:
    record = db.scalar(
        select(AuthState).where(AuthState.state_hash == _hash_state(state))
    )
    if not record or record.purpose != purpose:
        raise AuthStateError("登录 state 无效")
    if record.used_at is not None:
        raise AuthStateError("登录 state 已使用")
    expires_at = record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at <= datetime.now(UTC):
        raise AuthStateError("登录 state 已过期")
    record.used_at = datetime.now(UTC)
    db.commit()
    return record.return_path

