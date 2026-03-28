from dataclasses import dataclass


@dataclass(frozen=True)
class SetupMsg:
    """Coordinator sends this to B to initialise the session.

    In a real deployment this would be delivered over a trusted channel.
    w0 = H^t(password); t = total number of rounds available.
    """
    w0: str
    t: int


@dataclass(frozen=True)
class AuthenticateMsg:
    """Coordinator tells A to perform the next authentication round."""
    pass


@dataclass(frozen=True)
class AuthTokenMsg:
    """A sends (or an attacker forges) for round i.

    Carries: sender identity claim, round index, and the one-time value w_i.
    """
    sender: str
    round_i: int
    w_i: str


@dataclass(frozen=True)
class AuthResultMsg:
    """B sends back to A after verifying a token."""
    round_i: int
    accepted: bool
    reason: str


@dataclass(frozen=True)
class ShutdownMsg:
    pass


PartyMsg = SetupMsg | AuthenticateMsg | AuthTokenMsg | AuthResultMsg | ShutdownMsg
