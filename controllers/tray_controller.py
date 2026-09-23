from __future__ import annotations

from tkinter import messagebox
from typing import TYPE_CHECKING

from utils.i18n import _
import views.tray as tray

if TYPE_CHECKING:
    from .app_controller import AppController



RELEASE_MODEL_DELAY_MS = 30000


class TrayController:
    def __init__(self, app_controller: AppController) -> None:
        self.app = app_controller
        self.icon: tray.TrayIcon | None = None
        self.hidden = False
        self.__release_after_id: str | None = None

    def hide(self) -> None:
        if self.icon is None:
            self.icon = tray.create_tray(root=self.app.view, on_show=self.show, on_exit=self.app.destroy)
        if self.icon is None:
            messagebox.showinfo(_("提示"), _("托盘不可用，已直接关闭程序"))
            self.app.destroy()
            return
        self.hidden = True
        self.app.view.attributes("-alpha", 0)
        self.app.view.withdraw()
        self.schedule_release()

    def show(self) -> None:
        self.hidden = False
        self.__cancel_release()
        view = self.app.view
        view.after(50, lambda: view.attributes("-alpha", 1) or view.deiconify())

    def stop(self) -> None:
        self.hidden = False
        self.__cancel_release()
        if self.icon is not None:
            self.icon.stop()
            self.icon = None

    def schedule_release(self) -> None:
        if not self.hidden:
            return
        self.__cancel_release()
        self.__release_after_id = self.app.view.after(RELEASE_MODEL_DELAY_MS, self.__release_model)

    def __cancel_release(self) -> None:
        if self.__release_after_id is not None:
            self.app.view.after_cancel(self.__release_after_id)
            self.__release_after_id = None

    def __release_model(self) -> None:
        self.__release_after_id = None
        if not self.hidden:
            return
        tools = self.app.search_tools
        if tools is None or not tools.release_model():
            self.schedule_release()
