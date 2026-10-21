import ssl

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


def database_engine(database_url: str) -> AsyncEngine:
    """Share connection settings between the API and startup migrations."""
    url = make_url(database_url)
    if url.drivername == "postgresql+asyncpg" and (url.host or "").endswith(".neon.tech"):
        # Neon's console emits libpq parameters that asyncpg cannot accept as
        # keyword arguments. Verify the server certificate and hostname instead
        # of relying on libpq's sslmode/channel_binding options.
        url = url.difference_update_query(["sslmode", "channel_binding", "ssl"])
        return create_async_engine(
            url,
            pool_pre_ping=True,
            connect_args={"ssl": ssl.create_default_context(), "timeout": 15},
        )
    return create_async_engine(url, pool_pre_ping=True)
