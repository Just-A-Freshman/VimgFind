from __future__ import annotations

import ctypes
import ctypes.wintypes
from typing import Callable
import tkinter as tk


class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.wintypes.UINT),
        ("dwTime", ctypes.wintypes.DWORD),
    ]


class IdleMonitor:
    def __init__(self, root: tk.Tk | tk.Toplevel, threshold: int, on_idle: Callable[[], None]) -> None:
        self._root = root
        self._threshold = threshold
        self._on_idle = on_idle
        self._check_after_id: str | None = None
        self._was_idle: bool = False

        self.__last_input_info = _LASTINPUTINFO()
        self.__last_input_info.cbSize = ctypes.sizeof(_LASTINPUTINFO)
        self.__user32 = ctypes.windll.user32
        self.__kernel32 = ctypes.windll.kernel32

    def start(self) -> None:
        self._schedule_check()

    def stop(self) -> None:
        if self._check_after_id is not None:
            self._root.after_cancel(self._check_after_id)
            self._check_after_id = None

    def get_idle_seconds(self) -> float:
        if not self.__user32.GetLastInputInfo(ctypes.byref(self.__last_input_info)):
            return 0.0
        current_ticks = self.__kernel32.GetTickCount()
        elapsed = current_ticks - self.__last_input_info.dwTime
        return elapsed / 1000.0

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
