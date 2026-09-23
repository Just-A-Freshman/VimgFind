from __future__ import annotations

from typing import Callable, TYPE_CHECKING
import logging

import pystray
from PIL import Image

from config.settings import WinInfo
from utils.i18n import _

if TYPE_CHECKING:
    import tkinter as tk
    from pystray._base import Icon


class TrayIcon:
    def __init__(self, icon: Icon) -> None:
        self._icon = icon

    def notify(self, text: str) -> None:
        try:
            self._icon.notify(text)
        except Exception as e:
            logging.warning(f"托盘通知失败: {e}")

    def stop(self) -> None:
        try:
            self._icon.stop()
        except Exception as e:
            logging.warning(f"关闭托盘图标失败: {e}")


def create_tray(
    root: tk.Misc,
    on_show: Callable[[], None],
    on_exit: Callable[[], None],
) -> TrayIcon | None:
    try:
        with Image.open(WinInfo.icon_png) as source:
            image = source.convert("RGBA")
        icon = pystray.Icon(
            WinInfo.title,
            image,
            WinInfo.title,
            pystray.Menu(
                pystray.MenuItem(_("打开"), lambda: root.after(0, on_show), default=True),
                pystray.MenuItem(_("退出"), lambda: root.after(0, on_exit)),
            ),
        )
        tray = TrayIcon(icon)
        icon.run_detached(setup=lambda _: setattr(icon, "visible", True))
    except Exception as e:
        logging.error(f"托盘初始化失败: {e}")
        return None
    return tray
