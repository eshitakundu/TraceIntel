"""Who granted a permission, relative to the account that sent the transaction."""

from app.models.blockchain import OwnerRole, Transaction

ROLE_ORDER: dict[OwnerRole | None, int] = {"sender": 0, "called_contract": 1, None: 1, "other": 2}


def owner_role(owner: str, transaction: Transaction) -> OwnerRole:
    """Classify an approval owner.

    sender: the transaction's signer granted it; this is the sender's own exposure.
    called_contract: the contract the transaction called granted it. That can be the
        sender's smart wallet (e.g. a Safe) or a router acting on its own balance.
    other: another contract granted it while the transaction executed.
    """
    owner = owner.lower()
    if owner == transaction.sender:
        return "sender"
    if owner == transaction.recipient:
        return "called_contract"
    return "other"
