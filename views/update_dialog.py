from __future__ import annotations

from tkinter.ttk import Label, Progressbar
import tkinter as tk

from config.settings import WinInfo, TkS
from utils.i18n import _


class UpdateDialog(tk.Toplevel):
    status_label: Label
    progressbar: Progressbar
    hint_label: Label
    __slots__ = ("status_label", "progressbar", "hint_label")

    def __init__(self, parent) -> None:
        super().__init__(parent)
        self.__win(parent)
        self.status_label = self.__set_status_label()
        self.progressbar = self.__set_progressbar()
        self.hint_label = self.__set_hint_label()

    def __win(self, parent) -> None:
        self.withdraw()
        self.title(_("软件更新"))
        self.iconbitmap(WinInfo.ico_path)
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        win_w = TkS(380)
        win_h = TkS(130)
        x = parent.winfo_rootx() + (parent.winfo_width() - win_w) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - win_h) // 2
        self.geometry(f"{win_w}x{win_h}+{x}+{y}")
        self.deiconify()

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
