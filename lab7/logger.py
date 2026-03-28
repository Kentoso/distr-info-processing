import json
import time
from typing import Any

_LOG_LOCK = None


def set_log_lock(lock: Any) -> None:
    global _LOG_LOCK
    _LOG_LOCK = lock


def log_event(party: str, event: str, *, level: str = "INFO", **kwargs: Any) -> None:
    """Emit one JSON line to stdout. Thread/process-safe when lock is set."""
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


def print_result(scenario_name: str, rounds: list[dict]) -> None:
    """Human-readable scenario summary printed by the coordinator."""
    sep = "=" * 64
    print(f"\n{sep}")
    print(f"  RESULT: {scenario_name}")
    print(sep)
    for r in rounds:
        status = "[ACCEPTED]" if r["accepted"] else "[REJECTED]"
        sender = r.get("sender", "A")
        reason = r.get("reason", "")
        print(f"    {status}  round={r['round_i']}  sender={sender}  {reason}")
    print(sep)


# Canonical event name constants
EV_SCENARIO_START  = "scenario_start"
EV_SCENARIO_END    = "scenario_end"
EV_PARTY_START     = "party_start"
EV_PARTY_SHUTDOWN  = "party_shutdown"
EV_SETUP_DONE      = "setup_done"
EV_AUTH_SEND       = "auth_send"
EV_AUTH_VERIFY     = "auth_verify"
EV_AUTH_RESULT     = "auth_result_received"
EV_ATTACK_INJECT   = "attack_inject"
EV_EXHAUSTED       = "auth_exhausted"
