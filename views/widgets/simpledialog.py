"""macOS 适配的输入弹窗（simpledialog）。

- 按钮顺序遵循 macOS HIG：取消在左、确定在右（见 BasicDialog.buttonbox）；
- 置顶主窗口下提升弹窗层级，避免被遮挡（见 BasicDialog._raise_above_main，
  层级操作统一封装在 utils.macos_window）；
- 输入对话框逻辑复制自 CPython 3.12 tkinter/simpledialog.py 的 _QueryDialog，
  避免依赖 tkinter 私有类（_QueryString 等），控件改用 ttkbootstrap 统一风格。
"""
from __future__ import annotations

import tkinter as tk
from tkinter import simpledialog

from ttkbootstrap import Frame, Button, Label, Entry

from config.settings import WinInfo
from utils import macos_window, messagebox
from utils.i18n import _


class BasicDialog(simpledialog.Dialog):
    """tkinter.simpledialog.Dialog 的 macOS 适配基类。"""

    def buttonbox(self) -> None:
        box = Frame(self)
        box.pack(expand=True, fill=tk.X, pady=10)
        btn_cancel = Button(box, text=_("取消"), width=5, command=self.cancel, style="secondary")
        btn_save = Button(box, text=_("确定"), width=5, command=self.ok)
        box.grid_columnconfigure(0, weight=1)
        box.grid_columnconfigure(1, weight=0)
        box.grid_columnconfigure(2, weight=0)
        box.grid_columnconfigure(3, weight=1)
        btn_cancel.grid(row=0, column=1, padx=3, pady=3)
        btn_save.grid(row=0, column=2, padx=3, pady=3)
        self.bind("<Return>", self.ok)
        self.bind("<Escape>", self.cancel)
        WinInfo.set_window_icon(self)
        self.withdraw()
        self._raise_and_show()
        self.after_idle(self._maintain_above_main)

    def _raise_and_show(self):
        try:
            if not self.winfo_exists():
                return
            main = self.parent if self.parent is not None else tk._default_root
            if main is None or not main.attributes("-topmost"):
                self.deiconify()
                return
            if self._raise_above_main():
                self.deiconify()
            else:
                self.after(15, self._raise_and_show)
        except Exception:
            pass

    def _raise_above_main(self) -> bool:
        try:
            main = self.parent if self.parent is not None else tk._default_root
            if main is None or not main.attributes("-topmost"):
                return False
            return macos_window.raise_above_others({self.title()})
        except Exception:
            return False

    def _maintain_above_main(self):
        try:
            if not self.winfo_exists():
                return
            self._raise_above_main()
            self.after(300, self._maintain_above_main)
        except Exception:
            pass


class _QueryDialog(BasicDialog):
    """输入类对话框基类（复制自 CPython 3.12 tkinter/simpledialog.py 的 _QueryDialog）。"""

    errormessage = ""

    def __init__(self, title, prompt, initialvalue=None, minvalue=None, maxvalue=None, parent=None):
        self.prompt = prompt
        self.minvalue = minvalue
        self.maxvalue = maxvalue
        self.initialvalue = initialvalue
        super().__init__(parent, title)

    def destroy(self):
        self.entry = None
        super().destroy()

    def body(self, master):
        w = Label(master, text=self.prompt, justify=tk.LEFT)
        w.grid(row=0, padx=5, sticky=tk.W)
        self.entry = Entry(master, name="entry")
        self.entry.grid(row=1, padx=5, sticky=tk.W + tk.E)
        if self.initialvalue is not None:
            self.entry.insert(0, self.initialvalue)
            self.entry.select_range(0, tk.END)
        return self.entry

    def validate(self):
        try:
            result = self.getresult()
        except ValueError:
            messagebox.showwarning(
                "Illegal value",
                self.errormessage + "\nPlease try again",
                parent=self,
            )
            return 0
        if self.minvalue is not None and result < self.minvalue:
            messagebox.showwarning(
                "Too small",
                "The allowed minimum value is %s. Please try again." % self.minvalue,
                parent=self,
            )
            return 0
        if self.maxvalue is not None and result > self.maxvalue:
            messagebox.showwarning(
                "Too large",
                "The allowed maximum value is %s. Please try again." % self.maxvalue,
                parent=self,
            )
            return 0
        self.result = result
        return 1


class AskStringDialog(_QueryDialog):
    """字符串输入对话框（复制自 CPython _QueryString）。"""

    def validate(self):
        result = self.entry.get()
        self.result = result
        return 1

    def apply(self):
        pass


class AskFloatDialog(_QueryDialog):
    errormessage = "Not a floating point value."

    def getresult(self):
        return self.getfloat(self.entry.get())


class AskIntDialog(_QueryDialog):
    errormessage = "Not an integer."

    def getresult(self):
        return self.getint(self.entry.get())


def _query(dialog_cls, title, prompt, **kwargs):
    dialog = dialog_cls(title, prompt, **kwargs)
    return dialog.result


def askstring(title, prompt, **kwargs):
    return _query(AskStringDialog, title, prompt, **kwargs)


def askfloat(title, prompt, **kwargs):
    return _query(AskFloatDialog, title, prompt, **kwargs)


def askinteger(title, prompt, **kwargs):
    return _query(AskIntDialog, title, prompt, **kwargs)
