from __future__ import annotations

from typing import Callable
import tkinter as tk

from Quartz import (
    CGEventSourceSecondsSinceLastEventType,
    kCGAnyInputEventType,
    kCGEventSourceStateHIDSystemState,
)


class IdleMonitor:
    def __init__(self, root: tk.Tk | tk.Toplevel, threshold: int, on_idle: Callable[[], None]) -> None:
        self._root = root
        self._threshold = threshold
        self._on_idle = on_idle
        self._check_after_id: str | None = None
        self._was_idle: bool = False

    def start(self) -> None:
        self._schedule_check()

    def stop(self) -> None:
        if self._check_after_id is not None:
            self._root.after_cancel(self._check_after_id)
            self._check_after_id = None

    def get_idle_seconds(self) -> float:
        return CGEventSourceSecondsSinceLastEventType(
            kCGEventSourceStateHIDSystemState, kCGAnyInputEventType
        )

    def is_idle(self, threshold: float = 300.0) -> bool:
        return self.get_idle_seconds() >= threshold

    def _schedule_check(self) -> None:
        if self._check_after_id is not None:
            return
        self._check_after_id = self._root.after(1000, self._do_check)

    def _do_check(self) -> None:
        self._check_after_id = None
        now_idle = self.is_idle(self._threshold)
        if now_idle and not self._was_idle:
            self._on_idle()
        self._was_idle = now_idle
        self._schedule_check()
