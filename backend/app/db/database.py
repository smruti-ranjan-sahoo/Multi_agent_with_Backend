from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings


def _normalize_database_url(url: str) -> str:
    """Convert common Railway/Postgres URLs to an async SQLAlchemy URL."""
    if not url:
        return "sqlite+aiosqlite:///./app.db"

    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)

    if url.startswith("postgresql://") and "+asyncpg" not in url:
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)

    return url

# ── Engine ────────────────────────────────────────
engine_kwargs = {
    "echo": settings.DEBUG,
    "pool_pre_ping": True,
}

# SQLite async engine does not support pool sizing options used by Postgres.
if not settings.DATABASE_URL.startswith("sqlite"):
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20

DATABASE_URL = _normalize_database_url(settings.DATABASE_URL)
engine = create_async_engine(DATABASE_URL, **engine_kwargs)

# ── Session Factory ───────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# ── Base Model ────────────────────────────────────
class Base(DeclarativeBase):
    pass


# ── Dependency ────────────────────────────────────
async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── Create All Tables ─────────────────────────────
async def create_tables():
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as exc:
        # Keep the API bootable for healthchecks when DB is temporarily unavailable.
        print(f"⚠️ Database initialization skipped: {exc}")