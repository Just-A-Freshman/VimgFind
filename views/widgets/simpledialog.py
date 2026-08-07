from ttkbootstrap import Frame, Button
from tkinter import simpledialog
import tkinter as tk

from config.settings import TkS, WinInfo
from utils.i18n import _


# ── macOS 窗口层级适配 ─────────────────────────────────────────────
# macOS 上 -topmost 主窗口层级（19）高于普通对话框；overrideredirect 窗口（ToolTip）
# 又无法 -topmost。统一做法：把需要置顶显示的窗口（对话框/ToolTip）的 NSWindow level
# 提升到本应用最高层级 + 1，主窗口全程保持置顶不受影响。
# 系统文件对话框（filedialog）不在此列——带 parent 参数时 macOS 显示为 sheet，
# 天然显示在主窗口之上，无需任何层级操作。


def _app_windows() -> set:
    try:
        from AppKit import NSApp
        return set(NSApp.windows())
    except Exception:
        return set()


def _raise_windows_above_main(before: set) -> None:
    """把 before 之后新增的窗口（对话框）提升到本应用最高窗口层级 + 1。"""
    try:
        from AppKit import NSApp
        new = set(NSApp.windows()) - before
        if not new:
            return
        base = max((nw.level() for nw in NSApp.windows()), default=0)
        for nw in new:
            nw.setLevel_(base + 1)
    except Exception:
        pass


def patch_tooltip_topmost() -> None:
    """macOS: overrideredirect 窗口无法设置 -topmost，ToolTip 会被置顶主窗口遮挡。

    ttkbootstrap ToolTip 内部强制 overrideredirect=True，导致其 topmost=True 无效
    （Tk 8.6 在 macOS 上对 overrideredirect 窗口忽略 -topmost）。
    方案：ToolTip 显示时把它的 NSWindow level 提升到主窗口 level + 1，
    主窗口全程保持置顶不受影响；ToolTip 隐藏（destroy）后 level 随窗口销毁，无需恢复。
    """
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
                # 集合差：show 前后新增的 NSWindow 即 ToolTip 窗口（不依赖坐标，多显示器亦适用）
                new_windows = set(NSApp.windows()) - before
                if not new_windows:
                    return
                # 置顶主窗口为本应用最高层级窗口（Tk 8.6 置顶 level=19）；ToolTip 设为最高+1
                base = max((nw.level() for nw in NSApp.windows()), default=0)
                for nw in new_windows:
                    nw.setLevel_(base + 1)
            except Exception:
                pass

    ToolTip.show_tip = _show_tip
    ToolTip._vimgfind_tooltip_patched = True


# ── 自定义输入对话框 ───────────────────────────────────────────────


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


def _query(dialog_cls, title: str, prompt: str, **kwargs):
    parent = kwargs.get("parent") or tk._default_root
    before = _app_windows()
    timer = None
    if parent is not None:
        # wait_window 模态期间 Tk 事件循环仍在运行，after 回调会执行
        timer = parent.after(200, lambda: _raise_windows_above_main(before))
    try:
        dialog = dialog_cls(title, prompt, **kwargs)
        return dialog.result
    finally:
        if timer is not None:
            try:
                parent.after_cancel(timer)
            except Exception:
                pass


def askstring(title, prompt, **kwargs):
    return _query(AskStringDialog, title, prompt, **kwargs)

def askfloat(title, prompt, **kwargs):
    return _query(AskFloatDialog, title, prompt, **kwargs)

def askinteger(title, prompt, **kwargs):
    return _query(AskIntDialog, title, prompt, **kwargs)
