from dataclasses import dataclass
from enum import Enum
from typing import TypedDict, NewType


class ContractStatus(str, Enum):
    PENDING = "pending"
    REDEEMED = "redeemed"
    REFUNDED = "refunded"


class Asset(str, Enum):
    COIN_A = "CoinA"
    COIN_B = "CoinB"
    COIN_C = "CoinC"


class PartyName(str, Enum):
    A = "A"
    B = "B"
    C = "C"


class Contract(TypedDict):
    contract_id: str
    sender: PartyName
    receiver: PartyName
    asset: Asset
    amount: float
    hash_value: str   # SHA-256 hex of secret
    timeout: float    # absolute time.time() deadline
    status: ContractStatus
    secret: str | None


Balances = NewType("Balances", dict[PartyName, dict[Asset, float]])
Contracts = NewType("Contracts", dict[str, Contract])

INITIAL_AMOUNT = 100.0


# ---------------------------------------------------------------------------
# Inbox message models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CreateHtlcMsg:
    sender: PartyName
    receiver: PartyName
    asset: Asset
    amount: float
    hash_value: str
    timeout: float    # relative seconds from now
    contract_id: str


@dataclass(frozen=True)
class RedeemMsg:
    contract_id: str
    secret: str


@dataclass(frozen=True)
class RefundMsg:
    contract_id: str


@dataclass(frozen=True)
class ShutdownMsg:
    pass


PartyMsg = CreateHtlcMsg | RedeemMsg | RefundMsg | ShutdownMsg
