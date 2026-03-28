import multiprocessing as mp
from multiprocessing.synchronize import Lock as MpLock
import time

from models import (
    Asset,
    PartyName,
    PartyMsg,
    CreateHtlcMsg,
    RedeemMsg,
    RefundMsg,
    ShutdownMsg,
    INITIAL_AMOUNT,
)
from htlc import hash_secret, make_contract_id
from ledger import Ledger
from logger import (
    log_event,
    print_state,
    set_log_lock,
    EV_SCENARIO_START,
    EV_SCENARIO_END,
)
from party import Party


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _init_balances(manager_dict) -> None:
    """Each party starts with 100 of their own coin."""
    manager_dict[PartyName.A] = {Asset.COIN_A: INITIAL_AMOUNT}
    manager_dict[PartyName.B] = {Asset.COIN_B: INITIAL_AMOUNT}
    manager_dict[PartyName.C] = {Asset.COIN_C: INITIAL_AMOUNT}


def _make_parties(
    ledger: Ledger, log_lock: MpLock
) -> tuple[dict[PartyName, Party], dict[PartyName, "mp.Queue[PartyMsg]"]]:
    inboxes: dict[PartyName, mp.Queue[PartyMsg]] = {p: mp.Queue() for p in PartyName}
    parties = {
        p: Party(name=p.value, ledger=ledger, inbox=inboxes[p], log_lock=log_lock)
        for p in PartyName
    }
    return parties, inboxes


def _shutdown(
    parties: dict[PartyName, Party],
    inboxes: dict[PartyName, "mp.Queue[PartyMsg]"],
) -> None:
    for inbox in inboxes.values():
        inbox.put(ShutdownMsg())
    for p in parties.values():
        p.join()


# ---------------------------------------------------------------------------
# Scenario 1: Successful 3-party swap
# ---------------------------------------------------------------------------


def run_scenario_success(log_lock: MpLock) -> None:
    """
    A locks CoinA for B (T=9s)
    B locks CoinB for C (T=6s)
    C locks CoinC for A (T=3s)
    A redeems C→A revealing secret; B and C follow with the same secret.
    Final: A gets CoinC, B gets CoinA, C gets CoinB.
    """
    SECRET = "lab6_secret_alpha"
    H = hash_secret(SECRET)

    with mp.Manager() as manager:
        bal = manager.dict()
        con = manager.dict()
        _init_balances(bal)
        ledger = Ledger(bal, con)
        parties, inboxes = _make_parties(ledger, log_lock)

        id_ab = make_contract_id(PartyName.A, PartyName.B, Asset.COIN_A)
        id_bc = make_contract_id(PartyName.B, PartyName.C, Asset.COIN_B)
        id_ca = make_contract_id(PartyName.C, PartyName.A, Asset.COIN_C)

        log_event(
            "COORD",
            EV_SCENARIO_START,
            scenario="success",
            secret_hash=H,
            timeouts={"A->B": 9, "B->C": 6, "C->A": 3},
        )

        for p in parties.values():
            p.start()

        # Step 1: create all three HTLC contracts
        inboxes[PartyName.A].put(
            CreateHtlcMsg(
                sender=PartyName.A,
                receiver=PartyName.B,
                asset=Asset.COIN_A,
                amount=100.0,
                hash_value=H,
                timeout=9,
                contract_id=id_ab,
            )
        )
        time.sleep(0.2)

        inboxes[PartyName.B].put(
            CreateHtlcMsg(
                sender=PartyName.B,
                receiver=PartyName.C,
                asset=Asset.COIN_B,
                amount=100.0,
                hash_value=H,
                timeout=6,
                contract_id=id_bc,
            )
        )
        time.sleep(0.2)

        inboxes[PartyName.C].put(
            CreateHtlcMsg(
                sender=PartyName.C,
                receiver=PartyName.A,
                asset=Asset.COIN_C,
                amount=100.0,
                hash_value=H,
                timeout=3,
                contract_id=id_ca,
            )
        )
        time.sleep(0.2)

        # Step 2: A redeems C→A first (shortest timeout), revealing the secret
        inboxes[PartyName.A].put(RedeemMsg(contract_id=id_ca, secret=SECRET))
        time.sleep(0.2)

        # Step 3: B redeems B→C (secret now visible from id_ca)
        inboxes[PartyName.B].put(RedeemMsg(contract_id=id_bc, secret=SECRET))
        time.sleep(0.2)

        # Step 4: C redeems A→B
        inboxes[PartyName.C].put(RedeemMsg(contract_id=id_ab, secret=SECRET))
        time.sleep(0.2)

        _shutdown(parties, inboxes)
        log_event("COORD", EV_SCENARIO_END, scenario="success")
        print_state(
            "Scenario 1 — Successful Swap",
            ledger.snapshot_balances(),
            ledger.snapshot_contracts(),
        )


# ---------------------------------------------------------------------------
# Scenario 2: Timeout refund (C never creates its contract)
# ---------------------------------------------------------------------------


def run_scenario_timeout(log_lock: MpLock) -> None:
    """
    A locks CoinA for B (T=9s)
    B locks CoinB for C (T=6s)
    C never creates its contract — secret never revealed.
    After 6s B refunds; after 9s A refunds.
    Final: original balances unchanged.
    """
    SECRET = "lab6_secret_beta"
    H = hash_secret(SECRET)

    with mp.Manager() as manager:
        bal = manager.dict()
        con = manager.dict()
        _init_balances(bal)
        ledger = Ledger(bal, con)
        parties, inboxes = _make_parties(ledger, log_lock)

        id_ab = make_contract_id(PartyName.A, PartyName.B, Asset.COIN_A)
        id_bc = make_contract_id(PartyName.B, PartyName.C, Asset.COIN_B)

        log_event(
            "COORD",
            EV_SCENARIO_START,
            scenario="timeout",
            note="C will not create its contract",
        )

        for p in parties.values():
            p.start()

        inboxes[PartyName.A].put(
            CreateHtlcMsg(
                sender=PartyName.A,
                receiver=PartyName.B,
                asset=Asset.COIN_A,
                amount=100.0,
                hash_value=H,
                timeout=9,
                contract_id=id_ab,
            )
        )
        time.sleep(0.2)

        inboxes[PartyName.B].put(
            CreateHtlcMsg(
                sender=PartyName.B,
                receiver=PartyName.C,
                asset=Asset.COIN_B,
                amount=100.0,
                hash_value=H,
                timeout=6,
                contract_id=id_bc,
            )
        )

        # Wait for B's 6s lock to expire, then refund
        time.sleep(6.5)
        inboxes[PartyName.B].put(RefundMsg(contract_id=id_bc))

        # Wait for A's 9s lock (remaining time), then refund
        time.sleep(3.0)
        inboxes[PartyName.A].put(RefundMsg(contract_id=id_ab))

        time.sleep(0.2)
        _shutdown(parties, inboxes)
        log_event("COORD", EV_SCENARIO_END, scenario="timeout")
        print_state(
            "Scenario 2 — Timeout Refund (C absent)",
            ledger.snapshot_balances(),
            ledger.snapshot_contracts(),
        )


# ---------------------------------------------------------------------------
# Scenario 3: Wrong secret attempt, then correct redemption
# ---------------------------------------------------------------------------


def run_scenario_wrong_secret(log_lock: MpLock) -> None:
    """
    Full 3-contract setup.
    A first tries an incorrect secret on C→A — WARN logged, contract stays PENDING.
    A then uses the correct secret and the swap completes normally.
    Final: same rotation as Scenario 1.
    """
    SECRET = "lab6_secret_gamma"
    WRONG = "definitely_not_the_secret"
    H = hash_secret(SECRET)

    with mp.Manager() as manager:
        bal = manager.dict()
        con = manager.dict()
        _init_balances(bal)
        ledger = Ledger(bal, con)
        parties, inboxes = _make_parties(ledger, log_lock)

        id_ab = make_contract_id(PartyName.A, PartyName.B, Asset.COIN_A)
        id_bc = make_contract_id(PartyName.B, PartyName.C, Asset.COIN_B)
        id_ca = make_contract_id(PartyName.C, PartyName.A, Asset.COIN_C)

        log_event(
            "COORD",
            EV_SCENARIO_START,
            scenario="wrong_secret",
            note="A will first attempt redemption with wrong secret",
        )

        for p in parties.values():
            p.start()

        inboxes[PartyName.A].put(
            CreateHtlcMsg(
                sender=PartyName.A,
                receiver=PartyName.B,
                asset=Asset.COIN_A,
                amount=100.0,
                hash_value=H,
                timeout=9,
                contract_id=id_ab,
            )
        )
        time.sleep(0.2)

        inboxes[PartyName.B].put(
            CreateHtlcMsg(
                sender=PartyName.B,
                receiver=PartyName.C,
                asset=Asset.COIN_B,
                amount=100.0,
                hash_value=H,
                timeout=6,
                contract_id=id_bc,
            )
        )
        time.sleep(0.2)

        inboxes[PartyName.C].put(
            CreateHtlcMsg(
                sender=PartyName.C,
                receiver=PartyName.A,
                asset=Asset.COIN_C,
                amount=100.0,
                hash_value=H,
                timeout=3,
                contract_id=id_ca,
            )
        )
        time.sleep(0.2)

        # A tries wrong secret — fails with WARN, contract remains PENDING
        inboxes[PartyName.A].put(RedeemMsg(contract_id=id_ca, secret=WRONG))
        time.sleep(0.2)

        # A uses correct secret — succeeds
        inboxes[PartyName.A].put(RedeemMsg(contract_id=id_ca, secret=SECRET))
        time.sleep(0.2)

        inboxes[PartyName.B].put(RedeemMsg(contract_id=id_bc, secret=SECRET))
        time.sleep(0.2)

        inboxes[PartyName.C].put(RedeemMsg(contract_id=id_ab, secret=SECRET))
        time.sleep(0.2)

        _shutdown(parties, inboxes)
        log_event("COORD", EV_SCENARIO_END, scenario="wrong_secret")
        print_state(
            "Scenario 3 — Wrong Secret then Correct Redemption",
            ledger.snapshot_balances(),
            ledger.snapshot_contracts(),
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    mp.set_start_method("spawn", force=True)
    log_lock = mp.Lock()
    set_log_lock(log_lock)

    print("=== Lab 6: 3-Party HTLC Atomic Swap Simulation ===\n")

    run_scenario_success(log_lock)
    run_scenario_timeout(log_lock)
    run_scenario_wrong_secret(log_lock)


if __name__ == "__main__":
    main()
