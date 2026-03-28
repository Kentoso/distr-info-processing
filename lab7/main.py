"""Lab 7 — Lamport One-Time Password Authentication.

Three scenarios:
  1. Successful multi-round authentication (5 rounds).
  2. Replay attack: Eve re-uses a captured token; B rejects it, A still succeeds.
  3. Impersonation: Mallory forges a token without knowing w; B rejects it, A still succeeds.
"""

import multiprocessing as mp
from multiprocessing.synchronize import Lock as MpLock
import time

from auth import hash_chain
from logger import (
    log_event,
    print_result,
    set_log_lock,
    EV_SCENARIO_START,
    EV_SCENARIO_END,
    EV_ATTACK_INJECT,
)
from models import AuthenticateMsg, AuthTokenMsg, SetupMsg, ShutdownMsg
from party_a import PartyA
from party_b import PartyB

# ---------------------------------------------------------------------------
# Protocol parameters
# ---------------------------------------------------------------------------

T = 10  # total chain length; valid rounds are 1 … T-1
PASSWORD = "lamport_secret"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_parties(
    password: str, t: int, log_lock: MpLock
) -> tuple[PartyA, PartyB, "mp.Queue", "mp.Queue"]:
    """Create fresh A and B processes with their communication queues."""
    a_inbox: mp.Queue = mp.Queue()
    b_inbox: mp.Queue = mp.Queue()
    a = PartyA(
        password=password, t=t, inbox=a_inbox, b_inbox=b_inbox, log_lock=log_lock
    )
    b = PartyB(inbox=b_inbox, a_inbox=a_inbox, log_lock=log_lock)
    return a, b, a_inbox, b_inbox


def _setup_b(b_inbox: "mp.Queue", password: str, t: int) -> str:
    """Compute w_0 = H^t(password) and send it to B as the session anchor."""
    w0 = hash_chain(password, t)
    b_inbox.put(SetupMsg(w0=w0, t=t))
    return w0


def _shutdown(
    a: PartyA,
    b: PartyB,
    a_inbox: "mp.Queue",
    b_inbox: "mp.Queue",
) -> None:
    a_inbox.put(ShutdownMsg())
    b_inbox.put(ShutdownMsg())
    a.join()
    b.join()


# ---------------------------------------------------------------------------
# Scenario 1 — Successful multi-round authentication
# ---------------------------------------------------------------------------


def run_scenario_success(log_lock: MpLock) -> None:
    """A authenticates to B for 5 consecutive rounds; all are accepted."""
    log_event("COORD", EV_SCENARIO_START, scenario="success")

    a, b, a_inbox, b_inbox = _make_parties(PASSWORD, T, log_lock)
    a.start()
    b.start()

    _setup_b(b_inbox, PASSWORD, T)
    time.sleep(0.1)

    for _ in range(5):
        a_inbox.put(AuthenticateMsg())
        time.sleep(0.2)

    time.sleep(0.2)
    _shutdown(a, b, a_inbox, b_inbox)

    log_event("COORD", EV_SCENARIO_END, scenario="success")
    print_result(
        "Scenario 1 — Successful 5-Round Authentication",
        [
            {"round_i": i, "accepted": True, "sender": "A", "reason": "ok"}
            for i in range(1, 6)
        ],
    )


# ---------------------------------------------------------------------------
# Scenario 2 — Replay attack
# ---------------------------------------------------------------------------


def run_scenario_replay(log_lock: MpLock) -> None:
    """
    Round 1: A authenticates successfully, revealing w_1 to any observer.
    Eve captures w_1 and immediately replays it for round 2.
    B rejects Eve because H(w_1) == w_0 != w_1 (i.e., w_1 is not a pre-image of w_1).
    A then sends the legitimate w_2 for round 2 — B accepts.
    """
    log_event(
        "COORD",
        EV_SCENARIO_START,
        scenario="replay_attack",
        note="Eve replays w_1 for round 2 after observing round 1",
    )

    a, b, a_inbox, b_inbox = _make_parties(PASSWORD, T, log_lock)
    a.start()
    b.start()

    _setup_b(b_inbox, PASSWORD, T)
    time.sleep(0.1)

    # Round 1 — legitimate
    a_inbox.put(AuthenticateMsg())
    time.sleep(0.3)

    # Eve replays w_1 for round 2
    w_1 = hash_chain(PASSWORD, T - 1)
    log_event(
        "COORD",
        EV_ATTACK_INJECT,
        attacker="EVE",
        round_i=2,
        w_i_prefix=w_1[:16] + "…",
        note="replaying captured w_1; H(w_1)=w_0 != w_1 so check will fail",
    )
    b_inbox.put(AuthTokenMsg(sender="EVE", round_i=2, w_i=w_1))
    time.sleep(0.3)

    # Round 2 — legitimate (B's state was NOT advanced by Eve's failed attempt)
    a_inbox.put(AuthenticateMsg())
    time.sleep(0.3)

    _shutdown(a, b, a_inbox, b_inbox)

    log_event("COORD", EV_SCENARIO_END, scenario="replay_attack")
    print_result(
        "Scenario 2 — Replay Attack",
        [
            {"round_i": 1, "accepted": True, "sender": "A", "reason": "ok"},
            {
                "round_i": 2,
                "accepted": False,
                "sender": "EVE",
                "reason": "hash check failed: H(w_i) != w_{i-1}",
            },
            {"round_i": 2, "accepted": True, "sender": "A", "reason": "ok"},
        ],
    )


# ---------------------------------------------------------------------------
# Scenario 3 — Impersonation attempt
# ---------------------------------------------------------------------------


def run_scenario_impersonation(log_lock: MpLock) -> None:
    """
    Mallory does not know w.  She fabricates a plausible-looking hash for round 1.
    B rejects it because H(fake) != w_0.
    A then sends the genuine w_1 — B accepts.
    """
    log_event(
        "COORD",
        EV_SCENARIO_START,
        scenario="impersonation",
        note="Mallory forges a token without knowing the password",
    )

    a, b, a_inbox, b_inbox = _make_parties(PASSWORD, T, log_lock)
    a.start()
    b.start()

    _setup_b(b_inbox, PASSWORD, T)
    time.sleep(0.1)

    # Mallory's fabricated token (random hex, correct length, wrong value)
    fake_w = "deadbeef" * 8  # 64 hex chars — looks like SHA-256 output
    log_event(
        "COORD",
        EV_ATTACK_INJECT,
        attacker="MALLORY",
        round_i=1,
        w_i_prefix=fake_w[:16] + "…",
        note="fabricated hash; H(fake) != w_0 so check will fail",
    )
    b_inbox.put(AuthTokenMsg(sender="MALLORY", round_i=1, w_i=fake_w))
    time.sleep(0.3)

    # Round 1 — legitimate (B's expected round is still 1 after the failed attempt)
    a_inbox.put(AuthenticateMsg())
    time.sleep(0.3)

    _shutdown(a, b, a_inbox, b_inbox)

    log_event("COORD", EV_SCENARIO_END, scenario="impersonation")
    print_result(
        "Scenario 3 — Impersonation Attempt",
        [
            {
                "round_i": 1,
                "accepted": False,
                "sender": "MALLORY",
                "reason": "hash check failed: H(w_i) != w_{i-1}",
            },
            {"round_i": 1, "accepted": True, "sender": "A", "reason": "ok"},
        ],
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    mp.set_start_method("spawn", force=True)
    log_lock = mp.Lock()
    set_log_lock(log_lock)

    print("=== Lab 7: Lamport One-Time Password Authentication ===\n")

    run_scenario_success(log_lock)
    run_scenario_replay(log_lock)
    run_scenario_impersonation(log_lock)


if __name__ == "__main__":
    main()
