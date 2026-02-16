from copy import deepcopy
import time
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

        # Tracking for final report
        self.cw_sent: int = 0
        self.ccw_sent: int = 0
        self.rounds: int = 0

    def _log(self, msg: str):
        print(f"[{self.uid}]: {msg}")

    def _broadcast_out(self):
        message = Message(self.uid, Flag.OUT, 1 << self.phase)
        self.ccw.send(message)
        self.ccw_sent += 1
        self.cw.send(deepcopy(message))
        self.cw_sent += 1

    def _handle_leader(self, msg: LeaderMessage):
        if self.uid == msg.leader_uid:
            self._log("everyone knows that I'm the leader now!")
            return

        self.leader_uid = msg.leader_uid
        self._send_leader()

        self._log(f"did you know that {self.leader_uid} is the leader?")

    def _send_leader(self):
        if self.leader_uid is None or self.leader_forwarded:
            self._log(
                f"tried to send leader. {self.leader_uid=}, {self.leader_forwarded=}"
            )
            return

        leader_message = LeaderMessage(self.leader_uid)
        self.cw.send(leader_message)
        self.cw_sent += 1

        self.leader_forwarded = True

    def _out_message(self, msg: Message, forward_to: Connection, return_to: Connection):
        if msg.uid > self.uid:
            if msg.hop_count > 1:
                forwarded_message = Message(msg.uid, msg.flag, msg.hop_count - 1)
                forward_to.send(forwarded_message)
                if forward_to is self.cw:
                    self.cw_sent += 1
                else:
                    self.ccw_sent += 1
            elif msg.hop_count == 1:
                return_message = Message(msg.uid, Flag.IN, 1)
                return_to.send(return_message)
                if return_to is self.cw:
                    self.cw_sent += 1
                else:
                    self.ccw_sent += 1
        elif msg.uid == self.uid:
            self.status = Status.LEADER
            self._log("I'm the leader!")
            self.leader_uid = self.uid
            self._send_leader()

    def _handle_message(self, conn: Connection, msg: Message):
        self._log(f"got message: {msg}")

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
                self.got_in_from_ccw = False
                self.got_in_from_cw = False
                self._broadcast_out()
                return

            if msg.uid == self.uid:
                return

            forward_to = self.cw if from_ccw else self.ccw

            forward_to.send(Message(msg.uid, Flag.IN, 1))
            if forward_to is self.cw:
                self.cw_sent += 1
            else:
                self.ccw_sent += 1
            return

    def _print_final_report(self):
        total_sent = self.cw_sent + self.ccw_sent
        print(f"\n=== Final Report for Node {self.uid} ===")
        print(f"Leader UID: {self.leader_uid}")
        print(f"Messages sent CW: {self.cw_sent}")
        print(f"Messages sent CCW: {self.ccw_sent}")
        print(f"Total messages sent: {total_sent}")
        print(f"Total rounds: {self.rounds}")
        print("=" * 40)

    def run(self):
        self._broadcast_out()

        running = True
        while running:
            self.rounds += 1
            ready = wait([self.ccw, self.cw])

            for conn in ready:
                conn = cast(Connection, conn)

                msg: RingMessage = conn.recv()

                match msg:
                    case LeaderMessage():
                        self._handle_leader(msg)
                        running = False
                        break
                    case Message():
                        if self.leader_forwarded:
                            continue
                        self._handle_message(conn, msg)

        self._print_final_report()
        time.sleep(0.1)
