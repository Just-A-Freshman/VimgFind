from ttkbootstrap import Button, Frame, Label, Combobox, Checkbutton
from ttkbootstrap.constants import LINK
from ttkbootstrap.publisher import Publisher
import tkinter as tk

from config.settings import WinInfo, TkS
from utils.i18n import _


class SettingDialog(tk.Toplevel):
    theme_combobox: Combobox
    locale_combobox: Combobox
    maximize_checkbutton: Checkbutton
    topmost_checkbutton: Checkbutton
    open_settings_file_btn: Button
    check_update_btn: Button
    _instance = None
    __slots__ = (
        "theme_combobox", "locale_combobox",
        "maximize_checkbutton", "topmost_checkbutton",
        "open_settings_file_btn", "check_update_btn",
        "_initialized",
    )

    def __new__(cls, parent=None):
        if cls._instance is not None and cls._instance.winfo_exists():
            cls._instance.lift()
            cls._instance.focus_force()
            return cls._instance
        instance = super().__new__(cls)
        cls._instance = instance
        return instance
    
    def __init__(self, parent) -> None:
        if hasattr(self, '_initialized'):
            return
        super().__init__(parent)
        self.__win(parent)
        self._initialized = True
        self.theme_combobox = self.__set_theme_combobox()
        self.locale_combobox = self.__set_locale_combobox()
        self.maximize_checkbutton = self.__set_maximize_checkbutton()
        self.topmost_checkbutton = self.__set_topmost_checkbutton()
        self.open_settings_file_btn = self.__set_open_settings_file_btn()
        self.check_update_btn = self.__set_check_update_btn()
        self.__adjust_size()

    def __win(self, parent) -> None:
        self.withdraw()
        self.title(_("通用设置"))
        self.iconbitmap(WinInfo.ico_path)
        self.transient(parent)
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - TkS(220)) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - TkS(220)) // 2
        self.geometry(f"+{x}+{y}")
        self.minsize(TkS(200), TkS(180))
        self.deiconify()

    def __set_theme_combobox(self) -> Combobox:
        theme_setting_frame = Frame(self)
        theme_setting_frame.grid(row=1, column=1, columnspan=2, padx=(TkS(15), TkS(15)), pady=TkS(10), sticky=tk.W)
        Label(theme_setting_frame, text=_("界面主题：")).pack(side=tk.LEFT)
        combo = Combobox(theme_setting_frame, state="readonly", width=TkS(6), font=(WinInfo.default_font_family, WinInfo.default_font_size))
        combo.pack(side=tk.LEFT)
        return combo

    def __set_locale_combobox(self) -> Combobox:
        locale_frame = Frame(self)
        locale_frame.grid(row=2, column=1, columnspan=2, padx=(TkS(15), TkS(15)), pady=TkS(10), sticky=tk.W)
        Label(locale_frame, text=_("界面语言：")).pack(side=tk.LEFT)
        combo = Combobox(
            locale_frame, values=["中文", "English"], state="readonly", width=TkS(6),
            font=(WinInfo.default_font_family, WinInfo.default_font_size)
        )
        combo.pack(side=tk.LEFT)
        return combo

    def __set_maximize_checkbutton(self) -> Checkbutton:
        check_btn = Checkbutton(self, text=_("  启动时最大化窗口"))
        check_btn.grid(row=3, column=1, columnspan=4, pady=TkS(10), padx=(TkS(20), TkS(15)), sticky=tk.EW)
        return check_btn
    
    def __set_topmost_checkbutton(self) -> Checkbutton:
        check_btn = Checkbutton(self, text=_("  将当前窗口置顶"))
        check_btn.grid(row=4, column=1, columnspan=2, pady=TkS(10), padx=(TkS(20), TkS(15)), sticky=tk.EW)
        return check_btn

    def __set_check_update_btn(self) -> Button:
        check_update_btn = Button(self, text=_("检查更新"), takefocus=True, style=LINK, cursor="hand2")
        check_update_btn.grid(row=5, column=1, pady=TkS(10), padx=TkS(15), sticky=tk.W)
        return check_update_btn

    def __set_open_settings_file_btn(self) -> Button:
        open_settings_file_btn = Button(self, text=_("配置文件"), takefocus=True, style=LINK, cursor="hand2")
        open_settings_file_btn.grid(row=5, column=2, pady=TkS(10), padx=TkS(15))
        return open_settings_file_btn

    def __adjust_size(self) -> None:
        self.update_idletasks()
        bbox = self.grid_bbox()
        if bbox and bbox[2] > 0:
            win_w = bbox[0] + bbox[2] + TkS(10)
            win_h = bbox[1] + bbox[3] + TkS(10)
        else:
            return
        parent = self.master
        x = parent.winfo_rootx() + (parent.winfo_width() - win_w) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - win_h) // 2
        self.geometry(f"{win_w}x{win_h}+{x}+{y}")
        self.minsize(win_w, win_h)

    def destroy(self) -> None:
        Publisher.unsubscribe(str(self.theme_combobox))
        super().destroy()
