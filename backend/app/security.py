import secrets
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, Request, Response, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy.orm import Session

from .config import Settings, get_settings
from .db import get_db
from .models import User

SESSION_COOKIE = "filecode_session"


@dataclass(frozen=True)
class CurrentSession:
    user: User
    csrf_token: str


class SessionManager:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.serializer = URLSafeTimedSerializer(
            settings.session_secret,
            salt="file-code-session-v1",
        )

    def create(self, user: User) -> tuple[str, str]:
        csrf_token = secrets.token_urlsafe(24)
        token = self.serializer.dumps({"uid": user.id, "csrf": csrf_token})
        return token, csrf_token

    def read(self, token: str) -> dict[str, object]:
        try:
            return self.serializer.loads(
                token,
                max_age=self.settings.session_max_age_seconds,
            )
        except SignatureExpired as exc:
            raise HTTPException(status_code=401, detail="登录已过期，请重新登录") from exc
        except BadSignature as exc:
            raise HTTPException(status_code=401, detail="无效登录会话") from exc

    def set_cookie(self, response: Response, user: User) -> str:
        token, csrf_token = self.create(user)
        response.set_cookie(
            SESSION_COOKIE,
            token,
            max_age=self.settings.session_max_age_seconds,
            httponly=True,
            secure=self.settings.cookie_secure,
            samesite="lax",
            path="/",
        )
        return csrf_token

    def clear_cookie(self, response: Response) -> None:
        response.delete_cookie(
            SESSION_COOKIE,
            path="/",
            secure=self.settings.cookie_secure,
            httponly=True,
            samesite="lax",
        )


def get_session_manager(settings: Settings = Depends(get_settings)) -> SessionManager:
    return SessionManager(settings)


def get_current_session(
    request: Request,
    db: Session = Depends(get_db),
    manager: SessionManager = Depends(get_session_manager),
) -> CurrentSession:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="尚未登录")
    payload = manager.read(token)
    user_id = payload.get("uid")
    csrf_token = payload.get("csrf")
    if not isinstance(user_id, int) or not isinstance(csrf_token, str):
        raise HTTPException(status_code=401, detail="登录会话内容无效")
    user = db.get(User, user_id)
    if not user or not user.active:
        raise HTTPException(status_code=401, detail="用户不存在或已停用")
    if manager.settings.wecom_auth_mode == "live":
        expected_role = (
            "admin"
            if user.wecom_user_id.casefold()
            in manager.settings.wecom_admin_user_id_set
            else "user"
        )
        if user.role != expected_role:
            user.role = expected_role
            db.commit()
    return CurrentSession(user=user, csrf_token=csrf_token)


def require_user(session: CurrentSession = Depends(get_current_session)) -> User:
    return session.user


def require_admin(session: CurrentSession = Depends(get_current_session)) -> User:
    if session.user.role != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可执行此操作")
    return session.user


def require_csrf(
    session: CurrentSession = Depends(get_current_session),
    x_csrf_token: str | None = Header(default=None),
) -> CurrentSession:
    if not x_csrf_token or not secrets.compare_digest(x_csrf_token, session.csrf_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF 校验失败",
        )
    return session
