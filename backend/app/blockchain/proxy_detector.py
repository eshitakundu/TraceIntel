from app.blockchain.rpc_client import RpcClient

IMPLEMENTATION_SLOT = "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"
BEACON_SLOT = "0xa3f0ad74e5423aebfd80d3ef4346578335a9a72aeaee59ff6cb3582b35133d50"


def storage_address(value: str) -> str | None:
    if len(value) != 66 or int(value[2:26], 16) != 0:
        raise ValueError("Malformed proxy storage word")
    return "0x" + value[-40:].lower() if int(value, 16) else None


async def resolve_beacon(rpc: RpcClient, beacon: str, block: str) -> str | None:
    result = await rpc.call("eth_call", [{"to": beacon, "data": "0x5c60da1b"}, block])
    return storage_address(result)
