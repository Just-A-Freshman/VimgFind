from __future__ import annotations

from typing import Callable
import time
import tkinter as tk


class IdleTracker:
    def __init__(self, root: tk.Tk | tk.Toplevel, threshold: int, on_idle: Callable[[], None]) -> None:
        self._root = root
        self._threshold = threshold
        self._on_idle = on_idle
        self._last_interaction: float = time.monotonic()
        self._check_after_id: str | None = None
        self._bind_ids: list[str] = []
        self._was_idle: bool = False

    def start(self) -> None:
        self._last_interaction = time.monotonic()
        self._bind_ids = [
            self._root.bind_all("<Button-1>", self._on_interaction, add="+"),
            self._root.bind_all("<KeyPress>", self._on_interaction, add="+"),
            self._root.bind_all("<MouseWheel>", self._on_interaction, add="+"),
        ]
        self._schedule_check()

    def stop(self) -> None:
        if self._check_after_id is not None:
            self._root.after_cancel(self._check_after_id)
            self._check_after_id = None
        for bind_id in self._bind_ids:
            self._root.unbind_all(bind_id)
        self._bind_ids.clear()

    def is_idle(self) -> bool:
        return time.monotonic() - self._last_interaction >= self._threshold

    def reset_timer(self) -> None:
        self._last_interaction = time.monotonic()

    def _on_interaction(self, _event: tk.Event) -> None:
        self._last_interaction = time.monotonic()

    def _schedule_check(self) -> None:
        if self._check_after_id is not None:
            return
        self._check_after_id = self._root.after(1000, self._do_check)

    def _do_check(self) -> None:
        self._check_after_id = None
        now_idle = self.is_idle()
        if now_idle and not self._was_idle:
            self._on_idle()
        self._was_idle = now_idle
        self._schedule_check()
