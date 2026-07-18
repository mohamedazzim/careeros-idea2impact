import asyncio, asyncpg, os, pytest

DB_URL = os.getenv("DATABASE_URL", "")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not DB_URL,
        reason="DATABASE_URL is required for Postgres integration test",
    ),
]


def _parse_db_url(url):
    url = url.replace("postgresql+asyncpg://", "http://")
    url = url.replace("postgresql://", "http://")
    import urllib.parse
    p = urllib.parse.urlparse(url)
    return (
        p.username or "careeros",
        p.password or "careeros",
        p.hostname or "db",
        p.port or 5432,
        (p.path[1:] if p.path else "careeros_db"),
    )


@pytest.mark.asyncio
async def test_postgres_connection():
    user, password, host, port, database = _parse_db_url(DB_URL)
    c = await asyncpg.connect(
        user=user, password=password, database=database, host=host, port=port
    )
    ver = await c.fetchval("SELECT version()")
    assert ver is not None
    tables = await c.fetch(
        "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
    )
    print(f"DB: {ver[:50]}")
    print(f"TABLES ({len(tables)}):")
    for t in tables:
        print(f"  {t['tablename']}")
    await c.close()
