"""Seed verified learning resources into the database."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from src.db.session import async_session
from src.services.learning.learning_resource_service import get_learning_resource_service


async def main() -> None:
    service = get_learning_resource_service()
    async with async_session() as db:
        count = await service.ensure_seed_resources(db)
        print(f"Seeded {count} learning resources.")


if __name__ == "__main__":
    asyncio.run(main())
