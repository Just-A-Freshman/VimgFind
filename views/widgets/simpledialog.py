from typing import Literal
from tkinter import simpledialog
import tkinter as tk

from ttkbootstrap import Frame, Button, Checkbutton, Label

from config.settings import TkS
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
        self.after(50, lambda: self.attributes('-alpha', 1) or self.deiconify())


class AskCloseActionDialog(BasicDialog):
    def __init__(self, parent) -> None:
        self.close_action: Literal["ask", "tray", "ask"] = "ask"
        self.remember: tk.BooleanVar = tk.BooleanVar(value=False)
        self.result: tuple[Literal["ask", "tray", "ask"], bool] | None = None
        super().__init__(parent, title=_("关闭窗口"))

    def body(self, master) -> None:
        Label(master, text=_("请选择关闭方式：")).pack(pady=TkS(8))

    def buttonbox(self) -> None:
        box = Frame(self)
        upper_box = Frame(box)
        lower_box = Frame(box)
        buttons = ((_("直接关闭"), "primary", "exit"), (_("收到托盘"), "primary", "tray"), (_("取消"), "secondary", "ask"))
        for text, style, close_action in buttons:
            btn = Button(upper_box, text=text, takefocus=False, padding=(TkS(14), TkS(6)), style=style)
            btn.pack(side=tk.LEFT, padx=TkS(5))
            btn.config(command=lambda a=close_action: setattr(self, "result", (a, self.remember.get())) or self.ok())
        remember_btn = Checkbutton(lower_box, text=_("记住我的选择"), cursor="hand2", variable=self.remember)
        remember_btn.pack(pady=TkS(16))
        self.bind("<Escape>", lambda _: self.cancel())
        box.pack(expand=True, fill=tk.X, pady=TkS(10))
        upper_box.pack()
        lower_box.pack()    


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

def ask_close_action(parent) -> tuple[Literal["ask", "tray", "ask"], bool] | None:
    dialog = AskCloseActionDialog(parent)
    return dialog.result   
