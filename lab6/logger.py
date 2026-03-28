import json
import time
from typing import Any

from models import ContractStatus

_LOG_LOCK = None


def set_log_lock(lock: Any) -> None:
    global _LOG_LOCK
    _LOG_LOCK = lock


def log_event(party: str, event: str, *, level: str = "INFO", **kwargs: Any) -> None:
    """Emit one JSON line to stdout. Thread/process safe when lock is set."""
    record = {
        "ts": round(time.time(), 3),
        "party": party,
        "level": level,
        "event": event,
        **kwargs,
    }
    line = json.dumps(record, default=str)
    if _LOG_LOCK is not None:
        with _LOG_LOCK:
            print(line, flush=True)
    else:
        print(line, flush=True)


def print_state(
    scenario_name: str,
    balances: dict[str, dict[str, float]],
    contracts: list[dict],
) -> None:
    """Human-readable scenario summary printed by the coordinator."""
    sep = "=" * 64
    print(f"\n{sep}")
    print(f"  RESULT: {scenario_name}")
    print(sep)
    print("  Balances:")
    for party in sorted(balances):
        for asset, amount in sorted(balances[party].items()):
            print(f"    {party}.{asset} = {amount:.1f}")
    print("  Contracts:")
    markers = {
        ContractStatus.REDEEMED: "[REDEEMED]",
        ContractStatus.REFUNDED: "[REFUNDED]",
        ContractStatus.PENDING:  "[PENDING ]",
    }
    for c in contracts:
        marker = markers.get(c["status"], "[?      ]")
        sender = c["sender"].value if hasattr(c["sender"], "value") else c["sender"]
        receiver = c["receiver"].value if hasattr(c["receiver"], "value") else c["receiver"]
        asset = c["asset"].value if hasattr(c["asset"], "value") else c["asset"]
        print(
            f"    {marker}  {c['contract_id']}"
            f"  {sender}->{receiver}"
            f"  {asset} {c['amount']:.0f}"
        )
    print(sep)


# Canonical event name constants
EV_CONTRACT_CREATED = "contract_created"
EV_CREATE_FAIL = "create_fail"
EV_REDEEM_OK = "redeem_ok"
EV_REDEEM_FAIL = "redeem_fail"
EV_REFUND_OK = "refund_ok"
EV_REFUND_FAIL = "refund_fail"
EV_PARTY_START = "party_start"
EV_PARTY_SHUTDOWN = "party_shutdown"
EV_MSG_RECEIVED = "msg_received"
EV_SCENARIO_START = "scenario_start"
EV_SCENARIO_END = "scenario_end"
