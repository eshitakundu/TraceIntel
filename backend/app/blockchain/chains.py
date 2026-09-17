from pydantic import SecretStr

from app.config import Settings
from app.models.base import FrozenModel


class Chain(FrozenModel):
    slug: str
    chain_id: int
    name: str
    native_symbol: str
    explorer_url: str
    rpc_url: SecretStr


def chains(settings: Settings) -> dict[str, Chain]:
    return {
        "ethereum": Chain(
            slug="ethereum",
            chain_id=1,
            name="Ethereum",
            native_symbol="ETH",
            explorer_url="https://etherscan.io",
            rpc_url=settings.ethereum_rpc_url,
        ),
        "monad": Chain(
            slug="monad",
            chain_id=143,
            name="Monad",
            native_symbol="MON",
            explorer_url="https://monadvision.com",
            rpc_url=settings.monad_rpc_url,
        ),
    }
