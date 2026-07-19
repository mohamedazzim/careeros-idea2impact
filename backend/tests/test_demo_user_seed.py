from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.db import seed as seed_module
from src.schemas.security import Role


def _count_result(value: int = 0):
    result = MagicMock()
    result.scalar.return_value = value
    return result


@pytest.mark.asyncio
async def test_seed_demo_user_prefers_non_admin_demo_environment(monkeypatch):
    monkeypatch.setenv("SEED_DEMO_EMAIL", "judge-demo@example.com")
    monkeypatch.setenv("SEED_DEMO_PASSWORD", "not-logged")
    monkeypatch.setenv("SEED_DEMO_NAME", "CareerOS Demo User")
    monkeypatch.setenv("SEED_DEMO_ROLE", "User")
    monkeypatch.setenv("SEED_ADMIN_EMAIL", "legacy-admin@example.com")
    monkeypatch.setenv("SEED_ADMIN_PASSWORD", "legacy-password")
    monkeypatch.setenv("SEED_ADMIN_ROLE", "Admin")

    db = AsyncMock()
    db.execute.return_value = _count_result(0)
    repo = MagicMock()
    repo.get_by_email = AsyncMock(return_value=None)
    repo.create = AsyncMock(return_value=SimpleNamespace(id="demo-user-id"))
    monkeypatch.setattr(seed_module, "UserRepository", MagicMock(return_value=repo))
    monkeypatch.setattr(seed_module.auth_log, "log_event", MagicMock())

    await seed_module.seed_default_user(db)

    repo.get_by_email.assert_awaited_once_with("judge-demo@example.com")
    repo.create.assert_awaited_once()
    create_kwargs = repo.create.await_args.kwargs
    assert create_kwargs["email"] == "judge-demo@example.com"
    assert create_kwargs["full_name"] == "CareerOS Demo User"
    assert create_kwargs["role"] == Role.USER


@pytest.mark.asyncio
async def test_seed_demo_user_keeps_legacy_alias_defaulting_to_user(monkeypatch):
    monkeypatch.delenv("SEED_DEMO_EMAIL", raising=False)
    monkeypatch.delenv("SEED_DEMO_PASSWORD", raising=False)
    monkeypatch.delenv("SEED_DEMO_NAME", raising=False)
    monkeypatch.delenv("SEED_DEMO_ROLE", raising=False)
    monkeypatch.setenv("SEED_ADMIN_EMAIL", "legacy-demo@example.com")
    monkeypatch.setenv("SEED_ADMIN_PASSWORD", "not-logged")
    monkeypatch.setenv("SEED_ADMIN_NAME", "Legacy Demo User")
    monkeypatch.delenv("SEED_ADMIN_ROLE", raising=False)

    db = AsyncMock()
    db.execute.return_value = _count_result(0)
    repo = MagicMock()
    repo.get_by_email = AsyncMock(return_value=None)
    repo.create = AsyncMock(return_value=SimpleNamespace(id="legacy-demo-user-id"))
    monkeypatch.setattr(seed_module, "UserRepository", MagicMock(return_value=repo))
    monkeypatch.setattr(seed_module.auth_log, "log_event", MagicMock())

    await seed_module.seed_default_user(db)

    create_kwargs = repo.create.await_args.kwargs
    assert create_kwargs["email"] == "legacy-demo@example.com"
    assert create_kwargs["full_name"] == "Legacy Demo User"
    assert create_kwargs["role"] == Role.USER
