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


class SingletonDialog(tk.Toplevel):
    _instance = None
    def __new__(cls, parent=None):
        if cls._instance is not None and cls._instance.winfo_exists():
            cls._instance.lift()
            cls._instance.focus_force()
            return cls._instance
        instance = super().__new__(cls)
        cls._instance = instance
        return instance
    
    def __init__(self, *args, title: str = "", width: int = TkS(450), height: int = TkS(320), **kwargs) -> None:
        super().__init__(*args, **kwargs, background="black")
        self._initialized = True
        self.withdraw()
        self.attributes('-alpha', 0)
        self.update_idletasks()
        self.transient(self.master)  # type: ignore
        x = self.master.winfo_rootx() + (self.master.winfo_width() - width) // 2
        y = self.master.winfo_rooty() + (self.master.winfo_height() - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.title(title)
        self.after(100, lambda: self.attributes('-alpha', 1) or self.deiconify())


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
