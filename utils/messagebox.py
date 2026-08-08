from __future__ import annotations

import tkinter as tk
from tkinter import messagebox as _messagebox


from tkinter.messagebox import (  # noqa: F401
    ABORT, CANCEL, ERROR, INFO, IGNORE, NO, OK, OKCANCEL, QUESTION,
    RETRY, RETRYCANCEL, WARNING, YES, YESNO,
)


def _current_parent() -> tk.Misc | None:
    root = tk._default_root
    if root is None:
        return None
    try:
        fw = root.focus_get()
        if fw is not None:
            return fw.winfo_toplevel()
    except Exception:
        pass
    return root


def _wrap(name: str):
    orig = getattr(_messagebox, name)

    def wrapped(*args, **kwargs):
        if "parent" not in kwargs:
            parent = _current_parent()
            if parent is not None:
                kwargs["parent"] = parent
        return orig(*args, **kwargs)

    wrapped.__name__ = name
    wrapped.__doc__ = orig.__doc__
    return wrapped


showinfo = _wrap("showinfo")
showwarning = _wrap("showwarning")
showerror = _wrap("showerror")
askyesno = _wrap("askyesno")
askokcancel = _wrap("askokcancel")
askquestion = _wrap("askquestion")
askretrycancel = _wrap("askretrycancel")
