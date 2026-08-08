"""置顶窗口场景下的 ToolTip 子类。

macOS 上置顶主窗口（NSFloatingWindowLevel=19）会遮挡普通层级的 ToolTip 窗口；
本子类在显示后把提示窗口提升到当前最高层级之上。

替代原 patch_tooltip_topmost() 的全局 monkey-patch：不再修改第三方类的行为，
由本项目显式使用本子类创建 ToolTip。
"""
from __future__ import annotations

from ttkbootstrap.widgets import ToolTip

from utils import macos_window


class TopmostToolTip(ToolTip):
    """显示时若主窗口置顶，则把提示窗口提升到主窗口层级之上。"""

    def show_tip(self, *args, **kwargs) -> None:
        before = set(macos_window.windows())
        super().show_tip(*args, **kwargs)
        if self.toplevel is None:
            return
        try:
            if not self.widget.winfo_toplevel().attributes("-topmost"):
                return
            macos_window.raise_new_windows(before)
        except Exception:
            pass
