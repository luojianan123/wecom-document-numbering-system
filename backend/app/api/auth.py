from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..db import get_db
from ..models import User
from ..schemas import AuthStartOut, DevLoginIn, MeOut
from ..security import (
    CurrentSession,
    SessionManager,
    get_current_session,
    get_session_manager,
    require_csrf,
)
from ..services.auth_states import AuthStateError, consume_auth_state, issue_auth_state
from ..services.wecom import WeComError, wecom_client

router = APIRouter(prefix="/api", tags=["认证"])


def _find_or_create_user(db: Session, user_id: str, settings: Settings) -> User:
    user = db.scalar(select(User).where(User.wecom_user_id == user_id))
    role = "admin" if user_id in settings.wecom_admin_user_id_set else "user"
    if user:
        if user.role != role:
            user.role = role
        if not user.active:
            raise HTTPException(status_code=403, detail="当前成员已停用")
        db.commit()
        return user
    user = User(wecom_user_id=user_id, name=user_id, role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/auth/wecom/qr/start", response_model=AuthStartOut)
def start_qr_login(
    next_path: Annotated[str, Query(alias="next", max_length=512)] = "/",
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> AuthStartOut:
    if settings.wecom_auth_mode == "mock":
        return AuthStartOut(mode="mock")
    state = issue_auth_state(db, "qr", next_path)
    redirect_uri = f"{settings.backend_public_url.rstrip('/')}/api/auth/wecom/qr/callback"
    return AuthStartOut(
        mode="live",
        authorization_url=wecom_client.build_qr_authorization_url(redirect_uri, state),
    )


@router.get("/auth/wecom/qr/callback")
async def qr_callback(
    code: str,
    state: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    manager: SessionManager = Depends(get_session_manager),
) -> RedirectResponse:
    try:
        return_path = consume_auth_state(db, state, "qr")
        user_id = await wecom_client.get_user_id(code)
        user = _find_or_create_user(db, user_id, settings)
    except (AuthStateError, WeComError) as exc:
        query = urlencode({"auth_error": str(exc)})
        return RedirectResponse(
            url=f"{settings.frontend_url.rstrip('/')}/login?{query}",
            status_code=303,
        )
    response = RedirectResponse(
        url=f"{settings.frontend_url.rstrip('/')}{return_path}",
        status_code=303,
    )
    manager.set_cookie(response, user)
    return response


@router.post("/auth/dev-login", response_model=MeOut)
def dev_login(
    payload: DevLoginIn,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    manager: SessionManager = Depends(get_session_manager),
) -> MeOut:
    if settings.is_production or settings.wecom_auth_mode != "mock":
        raise HTTPException(status_code=404, detail="接口不存在")
    user = db.scalar(select(User).where(User.wecom_user_id == payload.user_id))
    if not user:
        user = User(
            wecom_user_id=payload.user_id,
            name=payload.name,
            role=payload.role,
        )
        db.add(user)
    else:
        user.name = payload.name
        user.role = payload.role
        user.active = True
    db.commit()
    db.refresh(user)
    csrf_token = manager.set_cookie(response, user)
    return MeOut(
        user=user,
        csrf_token=csrf_token,
        auth_mode=settings.wecom_auth_mode,
    )


@router.get("/me", response_model=MeOut)
def me(
    session: CurrentSession = Depends(get_current_session),
    settings: Settings = Depends(get_settings),
) -> MeOut:
    return MeOut(
        user=session.user,
        csrf_token=session.csrf_token,
        auth_mode=settings.wecom_auth_mode,
    )


@router.post("/auth/logout", status_code=204)
def logout(
    _: CurrentSession = Depends(require_csrf),
    manager: SessionManager = Depends(get_session_manager),
) -> Response:
    response = Response(status_code=204)
    manager.clear_cookie(response)
    return response
