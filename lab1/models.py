from dataclasses import dataclass
from enum import StrEnum
from typing import Literal, NewType

UID = NewType("UID", int)


class Flag(StrEnum):
    IN = "in"
    OUT = "out"


class Status(StrEnum):
    UNKNOWN = "unknown"
    LEADER = "leader"


@dataclass
class Message:
    uid: UID
    flag: Flag
    hop_count: int


@dataclass
class LeaderMessage:
    leader_uid: UID


RingMessage = Message | LeaderMessage
