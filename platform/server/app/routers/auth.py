import os
import secrets
import time
from collections import defaultdict
from datetime import datetime, timezone
from threading import Lock

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.dependencies import get_db
from app.models import User
from app.security import (
    SESSION_COOKIE,
    access_token_expire_minutes,
    cookie_secure,
    create_access_token,
    hash_password,
    require_user,
    validate_password,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

LEGAL_VERSION = "1.0"
RATE_LIMIT_MAX_FAILURES = 5
RATE_LIMIT_WINDOW_SECONDS = 15 * 60
FAILED_ATTEMPTS = defaultdict(list)
FAILED_ATTEMPTS_LOCK = Lock()


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)
    password_confirm: str = Field(min_length=1, max_length=256)
    is_admin: bool = False
    admin_code: str | None = None
    accept_terms: bool


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    role: str


class MessageResponse(BaseModel):
    message: str


def _ensure_user_table(db: Session) -> None:
    User.__table__.create(bind=db.get_bind(), checkfirst=True)


def _rate_limit_key(request: Request, action: str) -> str:
    host = request.client.host if request.client else "unknown"
    return f"{action}:{host}"


def _active_failures(key: str) -> list[float]:
    cutoff = time.monotonic() - RATE_LIMIT_WINDOW_SECONDS
    with FAILED_ATTEMPTS_LOCK:
        FAILED_ATTEMPTS[key] = [value for value in FAILED_ATTEMPTS[key] if value >= cutoff]
        return list(FAILED_ATTEMPTS[key])


def _check_rate_limit(key: str) -> None:
    if len(_active_failures(key)) >= RATE_LIMIT_MAX_FAILURES:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Trop de tentatives. Réessayez plus tard.",
        )


def _record_failure(key: str) -> None:
    with FAILED_ATTEMPTS_LOCK:
        FAILED_ATTEMPTS[key].append(time.monotonic())
        blocked = len(FAILED_ATTEMPTS[key]) >= RATE_LIMIT_MAX_FAILURES
    if blocked:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Trop de tentatives. Réessayez plus tard.",
        )


def _reset_failures(key: str) -> None:
    with FAILED_ATTEMPTS_LOCK:
        FAILED_ATTEMPTS.pop(key, None)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    _ensure_user_table(db)
    email = str(payload.email).strip().lower()

    if payload.password != payload.password_confirm:
        raise HTTPException(status_code=400, detail="Les mots de passe ne correspondent pas.")
    try:
        validate_password(payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not payload.accept_terms:
        raise HTTPException(status_code=400, detail="L'acceptation des conditions est obligatoire.")
    if db.query(User).filter(User.email == email).first() is not None:
        raise HTTPException(status_code=409, detail="Un compte utilise déjà cet email.")

    role = "user"
    if payload.is_admin:
        rate_key = _rate_limit_key(request, "admin-register")
        _check_rate_limit(rate_key)
        expected_code = os.getenv("ADMIN_SIGNUP_CODE", "").strip()
        if not expected_code:
            raise HTTPException(status_code=503, detail="Configuration administrateur indisponible.")
        received_code = payload.admin_code or ""
        if (
            len(received_code) != 6
            or not received_code.isdigit()
            or not secrets.compare_digest(received_code, expected_code)
        ):
            _record_failure(rate_key)
            raise HTTPException(status_code=403, detail="Code administrateur invalide.")
        _reset_failures(rate_key)
        role = "admin"

    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        role=role,
        is_active=True,
        terms_accepted_at=datetime.now(timezone.utc),
        legal_version=LEGAL_VERSION,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Un compte utilise déjà cet email.") from exc
    db.refresh(user)
    return user


@router.post("/login", response_model=UserResponse)
def login(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    _ensure_user_table(db)
    rate_key = _rate_limit_key(request, "login")
    _check_rate_limit(rate_key)
    email = str(payload.email).strip().lower()
    user = db.query(User).filter(User.email == email).first()

    if user is None or not verify_password(payload.password, user.password_hash):
        _record_failure(rate_key)
        raise HTTPException(status_code=401, detail="Email ou mot de passe incorrect.")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Compte désactivé.")

    _reset_failures(rate_key)
    response.set_cookie(
        key=SESSION_COOKIE,
        value=create_access_token(user.id),
        max_age=access_token_expire_minutes() * 60,
        httponly=True,
        secure=cookie_secure(),
        samesite="lax",
        path="/",
    )
    return user


@router.post("/logout", response_model=MessageResponse)
def logout(response: Response):
    response.delete_cookie(
        key=SESSION_COOKIE,
        path="/",
        secure=cookie_secure(),
        httponly=True,
        samesite="lax",
    )
    return {"message": "Déconnexion réussie"}


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(require_user)):
    return user
