import multiprocessing as mp
from multiprocessing.synchronize import Lock as MpLock

from auth import hash_chain
from logger import (
    log_event,
    set_log_lock,
    EV_PARTY_START,
    EV_PARTY_SHUTDOWN,
    EV_AUTH_SEND,
    EV_AUTH_RESULT,
    EV_EXHAUSTED,
)
from models import AuthenticateMsg, AuthTokenMsg, AuthResultMsg, ShutdownMsg, PartyMsg


class PartyA(mp.Process):
    """Authenticator — knows the secret password w and the chain length t.

    Computes w_i = H^(t-i)(w) on demand and sends AuthTokenMsg to B's inbox.
    Reacts to AuthResultMsg from B by logging the outcome.
    Never sends round t (which would expose the raw password w).
    """

    def __init__(
        self,
        password: str,
        t: int,
        inbox: "mp.Queue[PartyMsg]",
        b_inbox: "mp.Queue[PartyMsg]",
        log_lock: MpLock,
    ) -> None:
        super().__init__(daemon=False)
        self._password = password
        self._t = t
        self._inbox = inbox
        self._b_inbox = b_inbox
        self._log_lock = log_lock

    def run(self) -> None:
        set_log_lock(self._log_lock)
        log_event("A", EV_PARTY_START, t=self._t)
        round_counter = 1

        while True:
            msg: PartyMsg = self._inbox.get()
            match msg:
                case ShutdownMsg():
                    log_event("A", EV_PARTY_SHUTDOWN)
                    return

                case AuthenticateMsg():
                    if round_counter >= self._t:
                        log_event("A", EV_EXHAUSTED, round_i=round_counter, level="WARN",
                                  note="chain exhausted — refusing to send raw password")
                        continue
                    i = round_counter
                    w_i = hash_chain(self._password, self._t - i)
                    log_event("A", EV_AUTH_SEND, round_i=i, w_i_prefix=w_i[:16] + "…")
                    self._b_inbox.put(AuthTokenMsg(sender="A", round_i=i, w_i=w_i))
                    round_counter += 1

                case AuthResultMsg():
                    status = "ACCEPTED" if msg.accepted else "REJECTED"
                    log_event("A", EV_AUTH_RESULT, round_i=msg.round_i,
                              status=status, reason=msg.reason,
                              level="INFO" if msg.accepted else "WARN")
