import multiprocessing as mp
from multiprocessing.synchronize import Lock as MpLock

from auth import h
from logger import (
    log_event,
    set_log_lock,
    EV_PARTY_START,
    EV_PARTY_SHUTDOWN,
    EV_SETUP_DONE,
    EV_AUTH_VERIFY,
)
from models import SetupMsg, AuthTokenMsg, AuthResultMsg, ShutdownMsg, PartyMsg


class PartyB(mp.Process):
    """Verifier — stores the anchor w_{i-1} and the expected round counter i_A.

    For each incoming AuthTokenMsg it checks two conditions:
      1. round_i == i_expected
      2. H(w_i) == w_prev   (chain integrity)

    Only on success does it advance its state; failed attempts leave it unchanged
    so the legitimate authenticator can still succeed on the same round.
    """

    def __init__(
        self,
        inbox: "mp.Queue[PartyMsg]",
        a_inbox: "mp.Queue[PartyMsg]",
        log_lock: MpLock,
    ) -> None:
        super().__init__(daemon=False)
        self._inbox = inbox
        self._a_inbox = a_inbox
        self._log_lock = log_lock

    def run(self) -> None:
        set_log_lock(self._log_lock)
        log_event("B", EV_PARTY_START)

        # Phase 1: wait for the initial setup anchor
        setup: PartyMsg = self._inbox.get()
        assert isinstance(setup, SetupMsg), f"Expected SetupMsg, got {type(setup)}"
        w_prev = setup.w0
        i_expected = 1
        log_event("B", EV_SETUP_DONE, w0_prefix=setup.w0[:16] + "...", t=setup.t)

        while True:
            msg: PartyMsg = self._inbox.get()
            match msg:
                case ShutdownMsg():
                    log_event("B", EV_PARTY_SHUTDOWN)
                    return

                case AuthTokenMsg():
                    round_ok = msg.round_i == i_expected
                    hash_ok = h(msg.w_i) == w_prev

                    if not round_ok:
                        reason = (
                            f"round mismatch: expected {i_expected}, got {msg.round_i}"
                        )
                        accepted = False
                    elif not hash_ok:
                        reason = "hash check failed: H(w_i) != w_{i-1}"
                        accepted = False
                    else:
                        reason = "ok"
                        accepted = True

                    status = "ACCEPTED" if accepted else "REJECTED"
                    log_event(
                        "B",
                        EV_AUTH_VERIFY,
                        sender=msg.sender,
                        round_i=msg.round_i,
                        status=status,
                        reason=reason,
                        level="INFO" if accepted else "WARN",
                    )

                    if accepted:
                        w_prev = msg.w_i
                        i_expected += 1

                    self._a_inbox.put(
                        AuthResultMsg(
                            round_i=msg.round_i, accepted=accepted, reason=reason
                        )
                    )
