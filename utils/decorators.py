from __future__ import annotations
import functools
import logging
import sys
from queue import Queue
from threading import Thread
from typing import Callable


class QueueStream:
    def __init__(self, queue: Queue) -> None:
        self.queue = queue

    def write(self, message: str) -> None:
        clean_message = message.replace('\r', '').replace('\n', '').strip()
        if clean_message:
            self.queue.put(clean_message)

    def flush(self) -> None:
        pass


progress_queue: Queue = Queue()


def send_task(target):
    @functools.wraps(target)
    def inner(*args, **kwargs):
        def _wrapped():
            try:
                target(*args, **kwargs)
            except Exception as e:
                logging.error(f"后台任务 [{target.__name__}] 异常: {e}", exc_info=True)
        thread = Thread(target=_wrapped, daemon=True)
        thread.start()
    return inner


def redirect_output(target: Callable) -> Callable:
    def inner(*args, **kwargs) -> None:
        original_stdout = sys.stdout
        original_stderr = sys.stderr

        sys.stdout = QueueStream(progress_queue)
        sys.stderr = QueueStream(progress_queue)

        try:
            target(*args, **kwargs)
        finally:
            sys.stdout = original_stdout
            sys.stderr = original_stderr
    return inner
