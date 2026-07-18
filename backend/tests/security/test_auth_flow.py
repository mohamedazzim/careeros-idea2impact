"""End-to-end authentication flow tests.

Uses a minimal app with only the auth router mounted to avoid heavy imports.
"""
import sys
import types
import uuid
import inspect
from unittest.mock import AsyncMock, MagicMock, patch

# Pre-mock entire src.db.session so its module-level engine doesn't fire
import src.db  # noqa — ensures package exists
_ss = types.ModuleType("src.db.session")
_ss.engine = MagicMock()
_ss.async_session = MagicMock()
_ss.AsyncSession = AsyncMock

async def _fake_get_db():
    yield AsyncMock()

_ss.get_db = _fake_get_db
# Fix: import the actual types so sqlalchemy internals don't complain
from sqlalchemy.ext.asyncio import AsyncSession as RealAsyncSession
_ss.AsyncSession = RealAsyncSession
sys.modules["src.db.session"] = _ss

import httpx
import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
from sqlalchemy.exc import IntegrityError

# Build a minimal app with only the auth router
_mini_app = FastAPI()

# Import the auth router directly
from src.api.v1.endpoints.auth import router as auth_router
_mini_app.include_router(auth_router, prefix="/api/v1")

from src.core.exceptions.handlers import register_exception_handlers
register_exception_handlers(_mini_app)

from src.schemas.security import Token

# httpx compat
if "app" not in inspect.signature(httpx.Client.__init__).parameters:
    _orig = httpx.Client.__init__
    httpx.Client.__init__ = lambda self, *a, app=None, **kw: _orig(self, *a, **kw)

client = TestClient(_mini_app)


def _make_mock_user(**kw):
    uid = kw.pop("user_id", str(uuid.uuid4()))
    u = MagicMock()
    u.id = uuid.UUID(uid)
    u.email = kw.pop("email", "test@example.com")
    u.role = kw.pop("role", "User")
    u.password_hash = kw.pop("password_hash", "hashed_password")
    u.full_name = "Test User"
    u.failed_login_attempts = kw.pop("failed_login_attempts", 0)
    u.locked_until = kw.pop("locked_until", None)
    u.deleted_at = None
    return u


class TestRegister:
    def test_register_success(self):
        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        sys.modules["src.db.session"].get_db = lambda: _async_gen(mock_db)

        with patch(
            "src.db.repositories.user_repository.UserRepository.get_by_email",
            new_callable=AsyncMock,
        ) as mock_get:
            mock_get.return_value = None
            with patch(
                "src.db.repositories.user_repository.UserRepository.create",
                new_callable=AsyncMock,
            ) as mock_create:
                mock_create.return_value = _make_mock_user(email="newuser@example.com")
                with patch(
                    "src.services.security.auth.auth_service.generate_token_pair",
                    return_value=Token(access_token="ac", refresh_token="rf", expires_in=900),
                ):
                    resp = client.post("/api/v1/auth/register", json={
                        "email": "newuser@example.com",
                        "password": "Str0ng!Pass123",
                        "full_name": "New User",
                    })

        assert resp.status_code == 201
        assert "access_token" in resp.json()
        assert "careeros_token" in resp.cookies

    def test_register_duplicate_email(self):
        sys.modules["src.db.session"].get_db = lambda: _async_gen(AsyncMock())

        with patch(
            "src.db.repositories.user_repository.UserRepository.get_by_email",
            new_callable=AsyncMock,
        ) as mock_get:
            mock_get.return_value = _make_mock_user(email="exists@example.com")
            resp = client.post("/api/v1/auth/register", json={
                "email": "exists@example.com", "password": "Str0ng!Pass123",
            })

        assert resp.status_code == 409

    def test_register_duplicate_email_from_database_constraint(self):
        mock_db = AsyncMock()
        mock_db.rollback = AsyncMock()
        sys.modules["src.db.session"].get_db = lambda: _async_gen(mock_db)

        with patch(
            "src.db.repositories.user_repository.UserRepository.get_by_email",
            new_callable=AsyncMock,
        ) as mock_get:
            mock_get.return_value = None
            with patch(
                "src.db.repositories.user_repository.UserRepository.create",
                new_callable=AsyncMock,
            ) as mock_create:
                mock_create.side_effect = IntegrityError("insert users", {}, Exception("duplicate email"))
                resp = client.post("/api/v1/auth/register", json={
                    "email": "exists@example.com", "password": "Str0ng!Pass123",
                })

        assert resp.status_code == 409
        assert resp.json()["message"] == "Email already registered"

    def test_register_invalid_email(self):
        sys.modules["src.db.session"].get_db = lambda: _async_gen(AsyncMock())
        resp = client.post("/api/v1/auth/register", json={
            "email": "not-an-email", "password": "Str0ng!Pass123",
        })
        assert resp.status_code == 422
        assert "email" in str(resp.json()).lower()

    def test_register_weak_password(self):
        sys.modules["src.db.session"].get_db = lambda: _async_gen(AsyncMock())
        resp = client.post("/api/v1/auth/register", json={
            "email": "test@example.com", "password": "short",
        })
        assert resp.status_code in (400, 422)

    def test_register_email_normalized(self):
        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()
        sys.modules["src.db.session"].get_db = lambda: _async_gen(mock_db)

        with patch(
            "src.db.repositories.user_repository.UserRepository.get_by_email",
            new_callable=AsyncMock,
        ) as mock_get:
            mock_get.return_value = None
            with patch(
                "src.db.repositories.user_repository.UserRepository.create",
                new_callable=AsyncMock,
            ) as mock_create:
                mock_create.return_value = _make_mock_user(email="user@example.com")
                with patch(
                    "src.services.security.auth.auth_service.generate_token_pair",
                    return_value=Token(access_token="ac", refresh_token="rf", expires_in=900),
                ):
                    resp = client.post("/api/v1/auth/register", json={
                        "email": "  User@Example.COM  ", "password": "Str0ng!Pass123",
                    })

        assert resp.status_code == 201
        assert mock_create.call_args.kwargs["email"] == "user@example.com"


class TestLogin:
    def test_login_success(self):
        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()
        sys.modules["src.db.session"].get_db = lambda: _async_gen(mock_db)

        with patch(
            "src.db.repositories.user_repository.UserRepository.get_by_email",
            new_callable=AsyncMock,
        ) as mock_get:
            mock_get.return_value = _make_mock_user(email="user@example.com")
            with patch("src.api.v1.endpoints.auth._verify_password", return_value=True):
                with patch(
                    "src.services.security.auth.auth_service.generate_token_pair",
                    return_value=Token(access_token="xy", refresh_token="rz", expires_in=900),
                ):
                    resp = client.post("/api/v1/auth/login", json={
                        "email": "user@example.com", "password": "Str0ng!Pass123",
                    })

        assert resp.status_code == 200
        assert resp.json()["access_token"] == "xy"
        assert "careeros_token" in resp.cookies

    def test_login_wrong_password(self):
        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()
        sys.modules["src.db.session"].get_db = lambda: _async_gen(mock_db)

        with patch(
            "src.db.repositories.user_repository.UserRepository.get_by_email",
            new_callable=AsyncMock,
        ) as mock_get:
            mock_get.return_value = _make_mock_user(email="user@example.com")
            with patch("src.api.v1.endpoints.auth._verify_password", return_value=False):
                resp = client.post("/api/v1/auth/login", json={
                    "email": "user@example.com", "password": "WrongPass1!",
                })

        assert resp.status_code == 401

    def test_login_unknown_user(self):
        sys.modules["src.db.session"].get_db = lambda: _async_gen(AsyncMock())

        with patch(
            "src.db.repositories.user_repository.UserRepository.get_by_email",
            new_callable=AsyncMock,
        ) as mock_get:
            mock_get.return_value = None
            resp = client.post("/api/v1/auth/login", json={
                "email": "unknown@example.com", "password": "Str0ng!Pass123",
            })

        assert resp.status_code == 401

    def test_lockout_increments_on_failure(self):
        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()
        sys.modules["src.db.session"].get_db = lambda: _async_gen(mock_db)
        user = _make_mock_user(email="locked@example.com", failed_login_attempts=4)

        with patch(
            "src.db.repositories.user_repository.UserRepository.get_by_email",
            new_callable=AsyncMock,
        ) as mock_get:
            mock_get.return_value = user
            with patch("src.api.v1.endpoints.auth._verify_password", return_value=False):
                resp = client.post("/api/v1/auth/login", json={
                    "email": "locked@example.com", "password": "Str0ng!Pass123",
                })

        assert resp.status_code == 401
        assert user.failed_login_attempts == 5

    def test_login_already_locked(self):
        from datetime import datetime, timedelta

        sys.modules["src.db.session"].get_db = lambda: _async_gen(AsyncMock())
        user = _make_mock_user(
            email="locked@example.com",
            locked_until=datetime.utcnow() + timedelta(minutes=10),
        )

        with patch(
            "src.db.repositories.user_repository.UserRepository.get_by_email",
            new_callable=AsyncMock,
        ) as mock_get:
            mock_get.return_value = user
            resp = client.post("/api/v1/auth/login", json={
                "email": "locked@example.com", "password": "Str0ng!Pass123",
            })

        assert resp.status_code == 423

    def test_login_email_normalized(self):
        mock_db = AsyncMock()
        mock_db.commit = AsyncMock()
        sys.modules["src.db.session"].get_db = lambda: _async_gen(mock_db)

        with patch(
            "src.db.repositories.user_repository.UserRepository.get_by_email",
            new_callable=AsyncMock,
        ) as mock_get:
            mock_get.return_value = _make_mock_user(email="user@example.com")
            with patch("src.api.v1.endpoints.auth._verify_password", return_value=True):
                with patch(
                    "src.services.security.auth.auth_service.generate_token_pair",
                    return_value=Token(access_token="xy", refresh_token="rz", expires_in=900),
                ):
                    resp = client.post("/api/v1/auth/login", json={
                        "email": "  User@Example.COM  ", "password": "Str0ng!Pass123",
                    })

        assert resp.status_code == 200
        assert mock_get.call_args[0][0] == "user@example.com"


class TestTokenValidation:
    def test_me_requires_auth(self):
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    def test_me_with_valid_token(self):
        sys.modules["src.db.session"].get_db = lambda: _async_gen(AsyncMock())

        with patch("src.services.security.auth.auth_service.decode_token") as mock_decode:
            mock_decode.return_value = MagicMock(
                sub=str(uuid.uuid4()), role="User", type="access",
            )
            with patch(
                "src.db.repositories.user_repository.UserRepository.get_by_id",
                new_callable=AsyncMock,
            ) as mock_get_user:
                mock_get_user.return_value = _make_mock_user(email="user@example.com")
                resp = client.get(
                    "/api/v1/auth/me",
                    headers={"Authorization": "Bearer valid_token"},
                )

        assert resp.status_code == 200
        assert resp.json()["email"] == "user@example.com"


async def _async_gen(val):
    """Simulates an async generator for Depends(get_db)."""
    yield val
