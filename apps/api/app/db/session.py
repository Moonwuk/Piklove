from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings


def enforce_sqlite_foreign_keys(engine) -> None:
    """Turn on SQLite's per-connection foreign key enforcement.

    SQLite ignores FOREIGN KEY constraints unless each connection opts in, so
    without this every ON DELETE CASCADE in the schema is silently a no-op:
    DELETE /account/data reported success while leaving the account's
    conversations and retained message text on disk. PostgreSQL — the
    production database — enforces the constraints natively, which is why the
    gap only ever showed up on the SQLite default and never in a test.

    Safe to call on any engine; non-SQLite dialects are left alone.
    """
    sync_engine = getattr(engine, "sync_engine", engine)
    if sync_engine.dialect.name != "sqlite":
        return

    @event.listens_for(sync_engine, "connect")
    def _pragma_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


engine = create_async_engine(get_settings().database_url, pool_pre_ping=True)
enforce_sqlite_foreign_keys(engine)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db():
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
