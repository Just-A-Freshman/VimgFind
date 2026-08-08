from ttkbootstrap import Frame, Button
from tkinter import simpledialog
import tkinter as tk

from config.settings import TkS, WinInfo
from utils.i18n import _


# only necessary for macos
def patch_tooltip_topmost() -> None:
    try:
        from ttkbootstrap.widgets import ToolTip
    except ImportError:
        return
    if getattr(ToolTip, "_vimgfind_tooltip_patched", False):
        return

    _orig_show = ToolTip.show_tip

    def _show_tip(self, *args, **kwargs):
        try:
            from AppKit import NSApp
            before = set(NSApp.windows())
        except Exception:
            before = None
        _orig_show(self, *args, **kwargs)
        if before is not None and self.toplevel is not None:
            try:
                main = self.widget.winfo_toplevel()
                if not main.attributes("-topmost"):
                    return
                new_windows = set(NSApp.windows()) - before
                if not new_windows:
                    return
                base = max((nw.level() for nw in NSApp.windows()), default=0)
                for nw in new_windows:
                    nw.setLevel_(base + 1)
            except Exception:
                pass

    ToolTip.show_tip = _show_tip
    ToolTip._vimgfind_tooltip_patched = True




class BasicDialog(simpledialog.Dialog):
    def buttonbox(self) -> None:
        box = Frame(self)
        box.pack(expand=True, fill=tk.X, pady=10)
        btn_cancel = Button(box, text=_("取消"), width=TkS(5), command=self.cancel, style="secondary")
        btn_save = Button(box, text=_("确定"), width=TkS(5), command=self.ok)
        box.grid_columnconfigure(0, weight=1)
        box.grid_columnconfigure(1, weight=0)
        box.grid_columnconfigure(2, weight=0)
        box.grid_columnconfigure(3, weight=1)
        btn_cancel.grid(row=0, column=1, padx=TkS(3), pady=TkS(3))
        btn_save.grid(row=0, column=2, padx=TkS(3), pady=TkS(3))
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
            from AppKit import NSApp
            title = self.title()
            base = max((nw.level() for nw in NSApp.windows() if nw.title() != title), default=0)
            raised = False
            for nw in NSApp.windows():
                try:
                    if nw.title() == title:
                        nw.setLevel_(base + 1)
                        raised = True
                except Exception:
                    pass
            return raised
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


class AskStringDialog(BasicDialog, simpledialog._QueryString):    #type:ignore
    ...

class AskFloatDialog(BasicDialog, simpledialog._QueryFloat):   # type:ignore
    ...

class AskIntDialog(BasicDialog, simpledialog._QueryInteger):   #type:ignore
    ...


def _query(dialog_cls, title: str, prompt: str, **kwargs):
    dialog = dialog_cls(title, prompt, **kwargs)
    return dialog.result


def askstring(title, prompt, **kwargs):
    return _query(AskStringDialog, title, prompt, **kwargs)

def askfloat(title, prompt, **kwargs):
    return _query(AskFloatDialog, title, prompt, **kwargs)

def askinteger(title, prompt, **kwargs):
    return _query(AskIntDialog, title, prompt, **kwargs)
