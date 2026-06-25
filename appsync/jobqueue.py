"""A tiny serialized FIFO worker.

Mitigation for the shared Max account: never let two onboarding/deploy jobs
(and the Claude Code sessions they may trigger) run at once, so the shared
5-hour/weekly usage pool is not drained in one burst and concurrent logins
don't trip abuse detection. One worker thread, one job at a time.
"""
from __future__ import annotations

import logging
import queue
import threading
from collections.abc import Callable

log = logging.getLogger("appsync.queue")


class SerialWorker:
    def __init__(self, name: str = "appsync-worker"):
        self._q: "queue.Queue[Callable[[], None]]" = queue.Queue()
        self._thread = threading.Thread(target=self._run, name=name, daemon=True)
        self._started = False

    def start(self) -> None:
        if not self._started:
            self._started = True
            self._thread.start()

    def submit(self, job: Callable[[], None]) -> None:
        """Enqueue a job; it runs after every job submitted before it finishes."""
        self._q.put(job)

    def depth(self) -> int:
        return self._q.qsize()

    def _run(self) -> None:
        while True:
            job = self._q.get()
            try:
                job()
            except Exception:  # one bad job must not kill the worker
                log.exception("appsync job failed")
            finally:
                self._q.task_done()
