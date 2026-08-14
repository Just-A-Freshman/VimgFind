from __future__ import annotations

from tkinter.ttk import Label, Progressbar
import tkinter as tk

from config.settings import WinInfo, TkS
from views.widgets import simpledialog
from utils.i18n import _


class UpdateDialog(simpledialog.SingletonDialog):
    status_label: Label
    progressbar: Progressbar
    hint_label: Label
    __slots__ = ("status_label", "progressbar", "hint_label")

    def __init__(self, parent) -> None:
        if hasattr(self, '_initialized'):
            return
        super().__init__(parent, title=_("软件更新"), width=TkS(380), height=TkS(130))
        self.status_label = self.__set_status_label()
        self.progressbar = self.__set_progressbar()
        self.hint_label = self.__set_hint_label()

    def __set_status_label(self) -> Label:
        label = Label(self)
        label.pack(pady=(TkS(15), TkS(5)))
        return label

    def __set_progressbar(self) -> Progressbar:
        bar = Progressbar(self, mode="determinate", length=TkS(300))
        bar.pack(pady=TkS(5))
        return bar

    def __set_hint_label(self) -> Label:
        label = Label(self, text=_("关闭窗口可取消更新"))
        label.pack(pady=(TkS(5), TkS(10)))
        return label
