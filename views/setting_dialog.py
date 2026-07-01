from ttkbootstrap import Button, Style
from ttkbootstrap.constants import LINK
from ttkbootstrap.publisher import Publisher
from tkinter.ttk import Label, Combobox
import tkinter as tk

from settings import WinInfo


class SettingDialog(tk.Toplevel):
    def __init__(self, parent, setting) -> None:
        super().__init__(parent)
        self.withdraw()
        self.setting = setting

        self.title("通用设置")
        self.iconbitmap(WinInfo.ico_path)

        self.transient(parent)
        self.grab_set()

        self.theme_combo = self.__set_theme_selector()
        self.open_settings_file_btn = self.__set_open_settings_file_btn()
        self.check_update_btn = self.__set_check_update_btn()

        self.update_idletasks()
        win_w = min(self.winfo_reqwidth(), 400)
        win_h = self.winfo_reqheight() + 10
        x = parent.winfo_rootx() + (parent.winfo_width() - win_w) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - win_h) // 2
        self.geometry(f"{win_w}x{win_h}+{x}+{y}")
        self.minsize(win_w, win_h)
        self.deiconify()

    def __set_theme_selector(self) -> Combobox:
        Label(self, text="界面主题设置").grid(row=1, column=1, padx=(5, 10), sticky=tk.E)
        style = Style()
        theme_names = style.theme_names()
        combo = Combobox(self, values=theme_names, state="readonly", width=8)
        current_theme = self.setting.app.ui_style
        if current_theme in theme_names:
            combo.current(theme_names.index(current_theme))
        combo.grid(row=1, column=2, padx=(0, 10), sticky=tk.EW)
        return combo

    def __set_check_update_btn(self) -> Button:
        check_update_btn = Button(self, text="检查更新", takefocus=True, style=LINK, cursor="hand2")
        check_update_btn.grid(row=2, column=1, pady=(5, 0), sticky=tk.E)
        return check_update_btn

    def __set_open_settings_file_btn(self) -> Button:
        open_settings_file_btn = Button(self, text="配置文件", takefocus=True, style=LINK, cursor="hand2")
        open_settings_file_btn.grid(row=2, column=2, pady=(5, 0), padx=50, sticky=tk.W)
        return open_settings_file_btn

    def destroy(self) -> None:
        Publisher.unsubscribe(str(self.theme_combo))
        super().destroy()
