from collections.abc import Callable
from threading import Barrier, Thread


def raced(*jobs: Callable[[], None]) -> None:
    """Run every job in its own thread, all released from one barrier, and join them.

    The shape every contention test wants: the barrier makes the jobs actually
    overlap rather than run one after another, so a missing lock shows up as a
    torn artifact instead of passing by luck.

    jobs: the no-argument callables to race against each other.
    """
    start = Barrier(len(jobs))

    def entered(job: Callable[[], None]) -> None:
        start.wait()
        job()

    threads = [Thread(target=entered, args=(job,)) for job in jobs]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
