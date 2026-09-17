import json
from typing import Any

from app.blockchain.rpc_client import RpcClient, RpcError
from app.models.blockchain import Coverage, Evidence, Movement


async def fetch_traces(
    rpc: RpcClient, tx_hash: str, prefix: str, enabled: bool
) -> tuple[tuple[Movement, ...], tuple[Evidence, ...], Coverage]:
    if not enabled:
        return (
            (),
            (),
            Coverage(
                area="traces",
                status="unavailable",
                reason="Tracing disabled; internal movements and revert details unknown.",
            ),
        )
    try:
        trace = await rpc.call(
            "debug_traceTransaction", [tx_hash, {"tracer": "callTracer", "timeout": "5s"}]
        )
        encoded = json.dumps(trace)
        if len(encoded) > 2_000_000:
            raise RpcError("Trace exceeds report limit")
        if not isinstance(trace, dict) or "type" not in trace:
            raise RpcError("Unsupported trace format")
    except RpcError:
        return (
            (),
            (),
            Coverage(
                area="traces",
                status="unavailable",
                reason="Provider tracing unavailable; internal movements were not inferred.",
            ),
        )
    eid = f"{prefix}:trace"
    evidence = Evidence(
        id=eid,
        source="debug_traceTransaction / callTracer",
        description="Execution call tree; reverted branches excluded from movements",
        data_json=encoded,
    )
    movements: list[Movement] = []

    def visit(call: dict[str, Any], root: bool = False) -> None:
        if call.get("error"):
            return
        value = int(call.get("value", "0x0"), 16)
        if not root and value and call.get("to") and call["type"] in ("CALL", "CREATE", "CREATE2"):
            movements.append(
                Movement(
                    standard="native",
                    token="native",
                    sender=call["from"],
                    recipient=call["to"],
                    amount_raw=str(value),
                    decimals=18,
                    evidence_ids=(eid,),
                )
            )
        for child in call.get("calls", []):
            visit(child)

    visit(trace, root=True)
    return (
        tuple(movements),
        (evidence,),
        Coverage(
            area="traces",
            status="partial",
            reason="Call-tracer native value movements; delegate/static calls excluded. "
            "Not a full state-diff or balance reconciliation.",
        ),
    )
