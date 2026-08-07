from ttkbootstrap import Frame, Button
from tkinter import simpledialog
import tkinter as tk

from config.settings import TkS, WinInfo
from utils.i18n import _


class BasicDialog(simpledialog.Dialog):
    def buttonbox(self) -> None:
        box = Frame(self)
        box.pack(expand=True, fill=tk.X, pady=10)
        btn_save = Button(box, text=_("确定"), width=TkS(5), command=self.ok)
        btn_cancel = Button(box, text=_("取消"), width=TkS(5), command=self.cancel, style="secondary")
        box.grid_columnconfigure(0, weight=1)
        box.grid_columnconfigure(1, weight=0)
        box.grid_columnconfigure(2, weight=0)
        box.grid_columnconfigure(3, weight=1)
        btn_save.grid(row=0, column=1, padx=TkS(3), pady=TkS(3))
        btn_cancel.grid(row=0, column=2, padx=TkS(3), pady=TkS(3))
        self.bind("<Return>", self.ok)
        self.bind("<Escape>", self.cancel)
        WinInfo.set_window_icon(self)


class AskStringDialog(BasicDialog, simpledialog._QueryString):    #type:ignore
    ...

class AskFloatDialog(BasicDialog, simpledialog._QueryFloat):   # type:ignore
    ...

class AskIntDialog(BasicDialog, simpledialog._QueryInteger):   #type:ignore
    ...


def askstring(title, prompt, **kwargs):
    dialog = AskStringDialog(title, prompt, **kwargs)
    return dialog.result

def askfloat(title, prompt, **kwargs):
    dialog = AskFloatDialog(title, prompt, **kwargs)
    return dialog.result

def askinteger(title, prompt, **kwargs):
    dialog = AskIntDialog(title, prompt, **kwargs)
    return dialog.result
