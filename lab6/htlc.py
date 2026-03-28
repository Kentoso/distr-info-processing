import hashlib
import time
import uuid
from typing import cast

from models import Asset, Contract, ContractStatus, PartyName


def hash_secret(secret: str) -> str:
    """SHA-256 hex digest of secret string."""
    return hashlib.sha256(secret.encode()).hexdigest()


def verify_secret(secret: str, hash_value: str) -> bool:
    """Return True iff SHA-256(secret) == hash_value."""
    return hash_secret(secret) == hash_value


def make_contract_id(sender: PartyName, receiver: PartyName, asset: Asset) -> str:
    """Human-readable contract ID with unique suffix."""
    return f"{sender.value}->{receiver.value}:{asset.value}:{uuid.uuid4().hex[:6]}"


def create_contract(
    sender: PartyName,
    receiver: PartyName,
    asset: Asset,
    amount: float,
    hash_value: str,
    timeout_secs: float,
    contract_id: str | None = None,
) -> Contract:
    """Build a new Contract in PENDING state. timeout_secs is a relative duration."""
    return cast(
        Contract,
        {
            "contract_id": contract_id or make_contract_id(sender, receiver, asset),
            "sender": sender,
            "receiver": receiver,
            "asset": asset,
            "amount": amount,
            "hash_value": hash_value,
            "timeout": time.time() + timeout_secs,
            "status": ContractStatus.PENDING,
            "secret": None,
        },
    )


def redeem_contract(contract: Contract, secret: str) -> Contract:
    """
    Return updated contract in REDEEMED state.
    Raises ValueError on bad status, expired timeout, or wrong secret.
    Caller must write back to the ledger.
    """
    if contract["status"] != ContractStatus.PENDING:
        raise ValueError(f"Cannot redeem: status={contract['status']}")
    if time.time() > contract["timeout"]:
        raise ValueError("Cannot redeem: contract expired")
    if not verify_secret(secret, contract["hash_value"]):
        raise ValueError(f"Cannot redeem: wrong secret '{secret}'")
    updated = dict(contract)
    updated["status"] = ContractStatus.REDEEMED
    updated["secret"] = secret
    return cast(Contract, updated)


def refund_contract(contract: Contract) -> Contract:
    """
    Return updated contract in REFUNDED state.
    Raises ValueError on bad status or timeout not yet reached.
    Caller must write back to the ledger.
    """
    if contract["status"] != ContractStatus.PENDING:
        raise ValueError(f"Cannot refund: status={contract['status']}")
    if time.time() <= contract["timeout"]:
        raise ValueError("Cannot refund: timeout not yet expired")
    updated = dict(contract)
    updated["status"] = ContractStatus.REFUNDED
    return cast(Contract, updated)
