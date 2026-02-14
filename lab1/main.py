import multiprocessing as mp
import os


def _process():
    uid = os.getpid()
    print(uid)


if __name__ == "__main__":
    process = mp.Process(target=_process)
    process.start()
