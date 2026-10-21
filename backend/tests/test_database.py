import inspect
import ssl

import asyncpg
import pytest
from app.config import Settings
from app.storage.database import database_engine
from sqlalchemy import event


class ConnectionInspected(Exception):
    pass


@pytest.mark.asyncio
@pytest.mark.parametrize("pooled", [False, True])
async def test_neon_console_url_uses_verified_tls_with_asyncpg(pooled: bool) -> None:
    host = (
        "ep-test-pooler.ap-southeast-1.aws.neon.tech"
        if pooled
        else ("ep-test.ap-southeast-1.aws.neon.tech")
    )
    settings = Settings(
        database_url=f"postgresql://user:p%40ss@{host}/neondb?sslmode=require&channel_binding=require",
    )
    engine = database_engine(settings.database_url.get_secret_value())

    @event.listens_for(engine.sync_engine, "do_connect")
    def inspect_connection(dialect, record, args, kwargs):
        # Check the actual driver arguments, including kwargs SQLAlchemy adds.
        inspect.signature(asyncpg.connect).bind(*args, **kwargs)
        assert kwargs["password"] == "p@ss"
        assert kwargs["host"] == host
        context = kwargs["ssl"]
        assert isinstance(context, ssl.SSLContext)
        assert context.verify_mode == ssl.CERT_REQUIRED
        assert context.check_hostname is True
        raise ConnectionInspected

    try:
        with pytest.raises(ConnectionInspected):
            async with engine.connect():
                pass
    finally:
        await engine.dispose()
