import json
from typing import Any

from eth_abi.abi import decode
from eth_abi.exceptions import DecodingError
from eth_utils.crypto import keccak

from app.models.blockchain import Approval, Coverage, Evidence, Movement

TRANSFER = "0x" + keccak(text="Transfer(address,address,uint256)").hex()
APPROVAL = "0x" + keccak(text="Approval(address,address,uint256)").hex()
OPERATOR = "0x" + keccak(text="ApprovalForAll(address,address,bool)").hex()
SINGLE = "0x" + keccak(text="TransferSingle(address,address,address,uint256,uint256)").hex()
BATCH = "0x" + keccak(text="TransferBatch(address,address,address,uint256[],uint256[])").hex()
MAX_UINT256 = 2**256 - 1


def address(topic: str) -> str:
    if len(topic) != 66 or int(topic[2:26], 16) != 0:
        raise ValueError("Invalid indexed address")
    return "0x" + topic[-40:].lower()


def decode_events(
    logs: list[dict[str, Any]], prefix: str
) -> tuple[tuple[Movement, ...], tuple[Approval, ...], tuple[Evidence, ...], Coverage]:
    movements: list[Movement] = []
    approvals: list[Approval] = []
    evidence: list[Evidence] = []
    unknown = 0
    for position, log in enumerate(logs):
        eid = f"{prefix}:log:{int(log.get('logIndex', hex(position)), 16)}"
        evidence.append(
            Evidence(
                id=eid,
                source="eth_getTransactionReceipt.logs",
                description="Emitted event (standard pattern, not token attestation)",
                data_json=json.dumps(log, sort_keys=True),
            )
        )
        topics = log.get("topics", [])
        data = log.get("data", "0x")
        token = log["address"].lower()
        try:
            signature = topics[0].lower() if topics else ""
            if signature in (TRANSFER, APPROVAL) and len(topics) in (3, 4):
                nft = len(topics) == 4
                if (nft and data != "0x") or (not nft and len(data) != 66):
                    raise ValueError("Unexpected event layout")
                amount = int(topics[3] if nft else data, 16)
                sender, recipient = address(topics[1]), address(topics[2])
                if signature == TRANSFER:
                    movements.append(
                        Movement(
                            standard="ERC721" if nft else "ERC20",
                            token=token,
                            sender=sender,
                            recipient=recipient,
                            amount_raw="1" if nft else str(amount),
                            token_id=str(amount) if nft else None,
                            evidence_ids=(eid,),
                        )
                    )
                else:
                    approvals.append(
                        Approval(
                            standard="ERC721" if nft else "ERC20",
                            token=token,
                            owner=sender,
                            spender=recipient,
                            amount_raw=str(amount),
                            unlimited=not nft and amount == MAX_UINT256,
                            evidence_ids=(eid,),
                        )
                    )
            elif signature == OPERATOR and len(topics) == 3 and len(data) == 66:
                value = int(data, 16)
                if value not in (0, 1):
                    raise ValueError("Invalid boolean")
                approvals.append(
                    Approval(
                        standard="operator",
                        token=token,
                        owner=address(topics[1]),
                        spender=address(topics[2]),
                        amount_raw=str(value),
                        unlimited=bool(value),
                        evidence_ids=(eid,),
                    )
                )
            elif signature in (SINGLE, BATCH) and len(topics) == 4:
                values = decode(
                    ["uint256", "uint256"] if signature == SINGLE else ["uint256[]", "uint256[]"],
                    bytes.fromhex(data[2:]),
                )
                ids, amounts = ([values[0]], [values[1]]) if signature == SINGLE else values
                if len(ids) != len(amounts):
                    raise ValueError("Mismatched ERC1155 arrays")
                for token_id, amount in zip(ids, amounts, strict=True):
                    movements.append(
                        Movement(
                            standard="ERC1155",
                            token=token,
                            sender=address(topics[2]),
                            recipient=address(topics[3]),
                            amount_raw=str(amount),
                            token_id=str(token_id),
                            evidence_ids=(eid,),
                        )
                    )
            else:
                unknown += 1
        except (DecodingError, ValueError, OverflowError, IndexError):
            unknown += 1
    coverage = Coverage(
        area="events",
        status="partial" if unknown else "available",
        reason=f"{len(logs) - unknown}/{len(logs)} event layouts decoded. "
        "Event patterns do not prove token compliance.",
    )
    return tuple(movements), tuple(approvals), tuple(evidence), coverage
