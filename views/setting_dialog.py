from ttkbootstrap import Button, Frame, Label, Combobox, Checkbutton
from ttkbootstrap.constants import LINK
from ttkbootstrap.publisher import Publisher
import tkinter as tk

from settings import WinInfo, TkS


class SettingDialog(tk.Toplevel):
    theme_combobox: Combobox
    maximize_checkbutton: Checkbutton
    topmost_checkbutton: Checkbutton
    open_settings_file_btn: Button
    check_update_btn: Button
    _instance = None

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
        self.maximize_checkbutton = self.__set_maximize_checkbutton()
        self.topmost_checkbutton = self.__set_topmost_checkbutton()
        self.open_settings_file_btn = self.__set_open_settings_file_btn()
        self.check_update_btn = self.__set_check_update_btn()

    def __win(self, parent) -> None:
        self.withdraw()
        self.title("通用设置")
        self.iconbitmap(WinInfo.ico_path)
        self.transient(parent)
        self.update_idletasks()
        win_w = TkS(220)
        win_h = TkS(180)
        x = parent.winfo_rootx() + (parent.winfo_width() - win_w) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - win_h) // 2
        self.geometry(f"{win_w}x{win_h}+{x}+{y}")
        self.minsize(win_w, win_h)
        self.deiconify()

    def __set_theme_combobox(self) -> Combobox:
        theme_setting_frame = Frame(self)
        theme_setting_frame.grid(row=1, column=1, columnspan=2, padx=(TkS(15), TkS(15)), pady=TkS(10), sticky=tk.W)
        Label(theme_setting_frame, text="界面主题：").pack(side=tk.LEFT)
        combo = Combobox(theme_setting_frame, state="readonly", width=TkS(6), font=(WinInfo.default_font_family, WinInfo.default_font_size))
        combo.pack(side=tk.LEFT)
        return combo

    def __set_maximize_checkbutton(self) -> Checkbutton:
        check_btn = Checkbutton(self, text="  启动时最大化窗口")
        check_btn.grid(row=2, column=1, columnspan=2, pady=TkS(10), padx=(TkS(20), TkS(15)), sticky=tk.EW)
        return check_btn
    
    def __set_topmost_checkbutton(self) -> Checkbutton:
        check_btn = Checkbutton(self, text="  将当前窗口置顶")
        check_btn.grid(row=3, column=1, columnspan=2, pady=TkS(10), padx=(TkS(20), TkS(15)), sticky=tk.EW)
        return check_btn

    def __set_check_update_btn(self) -> Button:
        check_update_btn = Button(self, text="检查更新", takefocus=True, style=LINK, cursor="hand2")
        check_update_btn.grid(row=4, column=1, pady=TkS(10), padx=TkS(15), sticky=tk.W)
        return check_update_btn

    def __set_open_settings_file_btn(self) -> Button:
        open_settings_file_btn = Button(self, text="配置文件", takefocus=True, style=LINK, cursor="hand2")
        open_settings_file_btn.grid(row=4, column=2, pady=TkS(10), padx=TkS(15))
        return open_settings_file_btn

    def destroy(self) -> None:
        Publisher.unsubscribe(str(self.theme_combobox))
        super().destroy()
