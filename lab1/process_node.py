from models import UID, LeaderMessage, Message, RingMessage, Status, Flag
from multiprocessing.connection import Connection, wait
from typing import cast


class ProcessNode:
    def __init__(self, uid: UID, status: Status, ccw: Connection, cw: Connection):
        self.uid: UID = uid
        self.status: Status = status
        self.phase: int = 0

        self.ccw: Connection = ccw
        self.cw: Connection = cw

        self.got_in_from_cw: bool = False
        self.got_in_from_ccw: bool = False

        self.leader_uid: UID | None = None
        self.leader_forwarded: bool = False

    def _broadcast_out(self):
        message = Message(self.uid, Flag.OUT, 1 << self.phase)
        self.ccw.send(message)
        self.cw.send(message)

    def _handle_leader(self, conn: Connection, msg: LeaderMessage):
        pass

    def _out_message(self, msg: Message, forward_to: Connection, return_to: Connection):
        if msg.uid > self.uid:
            if msg.hop_count > 1:
                forwarded_message = Message(msg.uid, msg.flag, msg.hop_count - 1)
                forward_to.send(forwarded_message)
            elif msg.hop_count == 1:
                return_message = Message(msg.uid, Flag.IN, 1)
                return_to.send(return_message)
        elif msg.uid == self.uid:
            self.status = Status.LEADER

    def _handle_message(self, conn: Connection, msg: Message):
        from_ccw, from_cw = conn is self.ccw, conn is self.cw

        if msg.flag == Flag.OUT:
            forward_to = self.cw if from_ccw else self.ccw
            return_to = self.ccw if from_ccw else self.cw

            self._out_message(msg, forward_to, return_to)
            return

        if msg.flag == Flag.IN:
            self.got_in_from_ccw = self.got_in_from_ccw or (
                msg.uid == self.uid and from_ccw
            )
            self.got_in_from_cw = self.got_in_from_cw or (
                msg.uid == self.uid and from_cw
            )

            if self.got_in_from_ccw and self.got_in_from_cw:
                self.phase += 1
                self._broadcast_out()
                return

            if msg.uid == self.uid:
                return

            forward_to = self.cw if from_ccw else self.ccw

            forward_to.send(Message(msg.uid, Flag.IN, 1))
            return

    def run(self):
        self._broadcast_out()

        while True:
            ready = wait([self.ccw, self.cw])

            for conn in ready:
                conn = cast(Connection, conn)

                msg: RingMessage = conn.recv()

                match msg:
                    case LeaderMessage():
                        self._handle_leader(conn, msg)
                    case Message():
                        self._handle_message(conn, msg)
