import json
from typing import Any

from eth_abi.abi import decode
from eth_abi.exceptions import DecodingError
from eth_utils.crypto import keccak

from app.blockchain.signature_resolver import SIGNATURES


def json_value(value: Any) -> Any:
    if isinstance(value, bytes):
        return "0x" + value.hex()
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, (tuple, list)):
        return [json_value(item) for item in value]
    return value


def abi_type(item: dict[str, Any]) -> str:
    value = str(item["type"])
    if value.startswith("tuple"):
        return "(" + ",".join(abi_type(c) for c in item["components"]) + ")" + value[5:]
    return value


def decode_calldata(calldata: str, abi_json: str | None = None) -> tuple[str | None, str | None]:
    candidates = []
    if abi_json:
        for entry in json.loads(abi_json):
            if entry.get("type") == "function":
                inputs = entry.get("inputs", [])
                types = tuple(abi_type(item) for item in inputs)
                signature = entry["name"] + "(" + ",".join(types) + ")"
                if "0x" + keccak(text=signature).hex()[:8] == calldata[:10].lower():
                    candidates.append((signature, types, [item.get("name", "") for item in inputs]))
    known = SIGNATURES.get(calldata[:10].lower())
    if not candidates and known:
        candidates.append((known[0], known[1], [f"arg{i}" for i in range(len(known[1]))]))
    if len(candidates) != 1:
        return None, None
    signature, types, names = candidates[0]
    try:
        values = decode(types, bytes.fromhex(calldata[10:]), strict=True)
    except (DecodingError, ValueError, OverflowError):
        return None, None
    return signature, json.dumps(
        [
            {"name": name, "type": type_, "value": json_value(value)}
            for name, type_, value in zip(names, types, values, strict=True)
        ]
    )
