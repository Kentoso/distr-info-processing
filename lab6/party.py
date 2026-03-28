import multiprocessing as mp
from multiprocessing.synchronize import Lock as MpLock
import threading
import time

from htlc import create_contract, redeem_contract, refund_contract
from ledger import Ledger
from logger import (
    log_event,
    set_log_lock,
    EV_CONTRACT_CREATED,
    EV_CREATE_FAIL,
    EV_REDEEM_OK,
    EV_REDEEM_FAIL,
    EV_REFUND_OK,
    EV_REFUND_FAIL,
    EV_PARTY_START,
    EV_PARTY_SHUTDOWN,
    EV_MSG_RECEIVED,
)
from models import (
    ContractStatus,
    CreateHtlcMsg,
    PartyMsg,
    RedeemMsg,
    RefundMsg,
    WatchMsg,
    ShutdownMsg,
)


class Party(mp.Process):
    """
    A named participant in the atomic swap.
    Runs as a separate OS process and processes messages from its inbox queue.
    """

    def __init__(
        self,
        name: str,
        ledger: Ledger,
        inbox: "mp.Queue[PartyMsg]",
        log_lock: MpLock,
    ) -> None:
        super().__init__(name=name, daemon=False)
        self._party_name = name
        self._ledger = ledger
        self._inbox: mp.Queue[PartyMsg] = inbox
        self._log_lock = log_lock

    def run(self) -> None:
        # Initialize threading primitives here — threading.Lock can't be pickled
        # for spawn, so they must be created inside the child process.
        self._pending_watches: list[tuple[str, str]] = []  # (contract_id, hash_value)
        self._refund_watch: list[str] = []  # contract_ids to auto-refund
        self._state_lock = threading.Lock()  # guards both lists above
        set_log_lock(self._log_lock)  # must be called inside child process
        log_event(self._party_name, EV_PARTY_START)
        watcher = threading.Thread(target=self._watch_loop, daemon=True)
        watcher.start()
        self._loop()

    def _watch_loop(self) -> None:
        """Background thread: poll ledger every 100ms for auto-redeem and auto-refund."""
        while True:
            time.sleep(0.1)
            self._try_auto_redeem()
            self._try_auto_refund()

    def _try_auto_redeem(self) -> None:
        # Collect work under the lock, then act outside it so _handle_redeem
        # never runs while the lock is held (avoids re-entrancy issues).
        with self._state_lock:
            if not self._pending_watches:
                return
            all_contracts = self._ledger.snapshot_contracts()
            to_redeem: list[tuple[str, str]] = []  # (contract_id, secret)
            still_pending = []
            for contract_id, hash_value in self._pending_watches:
                secret = next(
                    (
                        c["secret"]
                        for c in all_contracts
                        if c["hash_value"] == hash_value and c["secret"] is not None
                    ),
                    None,
                )
                if secret is not None:
                    to_redeem.append((contract_id, secret))
                else:
                    still_pending.append((contract_id, hash_value))
            self._pending_watches = still_pending
        for contract_id, secret in to_redeem:
            self._handle_redeem(RedeemMsg(contract_id=contract_id, secret=secret))

    def _try_auto_refund(self) -> None:
        with self._state_lock:
            if not self._refund_watch:
                return
            now = time.time()
            to_refund: list[str] = []
            still_pending = []
            for contract_id in self._refund_watch:
                contract = self._ledger.get_contract(contract_id)
                if contract is None or contract["status"] != ContractStatus.PENDING:
                    continue  # already settled, drop from watch
                if now > contract["timeout"]:
                    to_refund.append(contract_id)
                else:
                    still_pending.append(contract_id)
            self._refund_watch = still_pending
        for contract_id in to_refund:
            self._handle_refund(RefundMsg(contract_id=contract_id))

    def _handle_watch(self, msg: WatchMsg) -> None:
        with self._state_lock:
            self._pending_watches.append((msg.contract_id, msg.hash_value))
        self._try_auto_redeem()  # check immediately in case already revealed

    def _loop(self) -> None:
        while True:
            msg: PartyMsg = self._inbox.get()
            log_event(
                self._party_name,
                EV_MSG_RECEIVED,
                msg_type=type(msg).__name__,
                contract_id=getattr(msg, "contract_id", None),
            )
            match msg:
                case CreateHtlcMsg():
                    self._handle_create(msg)
                case RedeemMsg():
                    self._handle_redeem(msg)
                case RefundMsg():
                    self._handle_refund(msg)
                case WatchMsg():
                    self._handle_watch(msg)
                case ShutdownMsg():
                    log_event(self._party_name, EV_PARTY_SHUTDOWN)
                    return

    def _handle_create(self, msg: CreateHtlcMsg) -> None:
        try:
            contract = create_contract(
                sender=msg.sender,
                receiver=msg.receiver,
                asset=msg.asset,
                amount=msg.amount,
                hash_value=msg.hash_value,
                timeout_secs=msg.timeout,
                contract_id=msg.contract_id,
            )
            self._ledger.add_contract(contract)
            with self._state_lock:
                self._refund_watch.append(contract["contract_id"])
            log_event(
                self._party_name,
                EV_CONTRACT_CREATED,
                contract_id=contract["contract_id"],
                sender=msg.sender,
                receiver=msg.receiver,
                asset=msg.asset,
                amount=msg.amount,
                deadline=round(contract["timeout"], 3),
            )
        except Exception as exc:
            log_event(
                self._party_name,
                EV_CREATE_FAIL,
                level="ERROR",
                error=str(exc),
            )

    def _handle_redeem(self, msg: RedeemMsg) -> None:
        contract = self._ledger.get_contract(msg.contract_id)
        if contract is None:
            log_event(
                self._party_name,
                EV_REDEEM_FAIL,
                level="ERROR",
                contract_id=msg.contract_id,
                reason="contract_not_found",
            )
            return
        try:
            updated = redeem_contract(contract, msg.secret)
            self._ledger.settle_redeem(updated)
            log_event(
                self._party_name,
                EV_REDEEM_OK,
                contract_id=msg.contract_id,
                secret=msg.secret,
                asset=updated["asset"],
                amount=updated["amount"],
                receiver=updated["receiver"],
            )
        except ValueError as exc:
            log_event(
                self._party_name,
                EV_REDEEM_FAIL,
                level="WARN",
                contract_id=msg.contract_id,
                secret=msg.secret,
                reason=str(exc),
            )

    def _handle_refund(self, msg: RefundMsg) -> None:
        contract = self._ledger.get_contract(msg.contract_id)
        if contract is None:
            log_event(
                self._party_name,
                EV_REFUND_FAIL,
                level="ERROR",
                contract_id=msg.contract_id,
                reason="contract_not_found",
            )
            return
        try:
            updated = refund_contract(contract)
            self._ledger.settle_refund(updated)
            log_event(
                self._party_name,
                EV_REFUND_OK,
                contract_id=msg.contract_id,
                asset=updated["asset"],
                amount=updated["amount"],
                sender=updated["sender"],
            )
        except ValueError as exc:
            log_event(
                self._party_name,
                EV_REFUND_FAIL,
                level="WARN",
                contract_id=msg.contract_id,
                reason=str(exc),
            )
