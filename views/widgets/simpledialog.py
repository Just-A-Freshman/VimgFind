from ttkbootstrap import Frame, Button
from tkinter import simpledialog
import tkinter as tk

from config.settings import TkS, WinInfo
from utils.i18n import _


# ── macOS 窗口层级适配 ─────────────────────────────────────────────
# macOS 上 -topmost 主窗口层级高于普通对话框。
# - 普通 Toplevel（simpledialog 弹窗）：直接设置 attributes("-topmost", True) 即可
#   （Tk 原生持续管理，不会像 NSWindow setLevel_ hack 那样被窗口激活重置）。
# - overrideredirect 窗口（ToolTip）：-topmost 在 macOS 上无效（Tk 8.6 限制），
#   只能通过提升 NSWindow level 实现（见 patch_tooltip_topmost）。
# - 系统文件对话框（filedialog）：带 parent 时显示为 sheet，天然在父窗口之上。


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
        # macOS HIG: 取消在左、确定在右
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
        # 主窗口置顶时弹窗自身提升到最高层级+1：simpledialog.Dialog 内置 transient，
        # 其窗口的 -topmost 在 macOS 上永久无效、NSWindow level 会被 Tk 设为 0。
        # 弹窗 NSWindow 在创建后约 40ms 才注册到 NSApp.windows()，若先显示再提升会
        # 经历"先显示→被遮挡→再显示"的闪烁。因此先隐藏窗口，等 NSWindow 注册并
        # 提升成功后（level > 置顶主窗口）再显示。
        self.withdraw()
        self._raise_and_show()
        self.after_idle(self._maintain_above_main)

    def _raise_and_show(self):
        try:
            if not self.winfo_exists():
                return
            main = self.parent if self.parent is not None else tk._default_root
            if main is None or not main.attributes("-topmost"):
                self.deiconify()  # 非置顶：无需提升，直接显示
                return
            if self._raise_above_main():
                self.deiconify()
            else:
                self.after(15, self._raise_and_show)
        except Exception:
            pass

    def _raise_above_main(self) -> bool:
        """将本弹窗的 NSWindow level 提升到本应用最高层级 + 1（高于置顶主窗口）。"""
        try:
            # AskString/Int/Float 的继承链（_QueryBase.__init__）会吞掉 parent 参数，
            # self.parent 可能为 None，回退到默认根窗口（主窗口）
            main = self.parent if self.parent is not None else tk._default_root
            if main is None or not main.attributes("-topmost"):
                return False
            from AppKit import NSApp
            title = self.title()
            # base 取其他窗口（排除弹窗自身）的最高层级，避免维护循环中 level 无限递增
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
    # 弹窗置顶在 BasicDialog.buttonbox 内处理（Tk 原生 -topmost），无需 after 定时器/NSWindow hack
    dialog = dialog_cls(title, prompt, **kwargs)
    return dialog.result


def askstring(title, prompt, **kwargs):
    return _query(AskStringDialog, title, prompt, **kwargs)

def askfloat(title, prompt, **kwargs):
    return _query(AskFloatDialog, title, prompt, **kwargs)

def askinteger(title, prompt, **kwargs):
    return _query(AskIntDialog, title, prompt, **kwargs)
