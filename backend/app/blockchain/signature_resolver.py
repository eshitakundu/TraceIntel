from eth_abi.abi import decode
from eth_abi.exceptions import DecodingError

SIGNATURES = {
    "0x095ea7b3": ("approve(address,uint256)", ("address", "uint256")),
    "0xa9059cbb": ("transfer(address,uint256)", ("address", "uint256")),
    "0x23b872dd": ("transferFrom(address,address,uint256)", ("address", "address", "uint256")),
    "0xa22cb465": ("setApprovalForAll(address,bool)", ("address", "bool")),
    "0x42842e0e": ("safeTransferFrom(address,address,uint256)", ("address", "address", "uint256")),
}


def resolve(calldata: str) -> str | None:
    entry = SIGNATURES.get(calldata[:10].lower())
    if not entry:
        return None
    try:
        decode(entry[1], bytes.fromhex(calldata[10:]), strict=True)
    except (DecodingError, ValueError, OverflowError):
        return None
    return entry[0]
