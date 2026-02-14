import multiprocessing as mp
from multiprocessing.connection import Connection
from typing import Callable
import os

from models import UID, Status
from process_node import ProcessNode


def create_ring_processes(
    n: int,
    target: Callable[[Connection, Connection], None],
) -> list[mp.Process]:
    if n < 2:
        raise ValueError("Ring needs at least 2 processes")

    edge_ends: list[tuple[Connection, Connection]] = [  # pyright: ignore[reportAssignmentType]
        mp.Pipe(duplex=True) for _ in range(n)
    ]

    procs: list[mp.Process] = []
    for i in range(n):
        cw_conn = edge_ends[i][0]
        ccw_conn = edge_ends[(i - 1) % n][1]

        p = mp.Process(target=target, args=(ccw_conn, cw_conn))
        p.start()
        procs.append(p)

    return procs


def _process(ccw: Connection, cw: Connection):
    uid = os.getpid()
    # print(f"[{uid}] started", flush=True)

    # cw.send(("hello", uid))
    # msg = ccw.recv()
    # print(f"[{uid}] got {msg}", flush=True)

    node = ProcessNode(UID(uid), Status.UNKNOWN, ccw, cw)
    node.run()


if __name__ == "__main__":
    procs = create_ring_processes(5, _process)
    for p in procs:
        p.join()
