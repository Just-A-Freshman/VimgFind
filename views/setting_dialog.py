from ttkbootstrap import Button, Frame, Label, Combobox, Checkbutton
from ttkbootstrap.constants import LINK
from ttkbootstrap.publisher import Publisher
import tkinter as tk

from settings import WinInfo


class SettingDialog(tk.Toplevel):
    theme_combobox: Combobox
    maximize_checkbutton: Checkbutton
    open_settings_file_btn: Button
    check_update_btn: Button
    
    def __init__(self, parent) -> None:
        super().__init__(parent)
        self.__win(parent)
        self.theme_combobox = self.__set_theme_combobox()
        self.maximize_checkbutton = self.__set_maximize_checkbutton()
        self.open_settings_file_btn = self.__set_open_settings_file_btn()
        self.check_update_btn = self.__set_check_update_btn()

    def __win(self, parent) -> None:
        self.withdraw()
        self.title("通用设置")
        self.iconbitmap(WinInfo.ico_path)
        self.transient(parent)
        self.update_idletasks()
        win_w = 350
        win_h = 250
        x = parent.winfo_rootx() + (parent.winfo_width() - win_w) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - win_h) // 2
        self.geometry(f"{win_w}x{win_h}+{x}+{y}")
        self.minsize(win_w, win_h)
        self.deiconify()

    def __set_theme_combobox(self) -> Combobox:
        theme_setting_frame = Frame(self)
        theme_setting_frame.grid(row=1, column=1, columnspan=2, padx=(30, 30), pady=20, sticky=tk.W)
        Label(theme_setting_frame, text="界面主题：").pack(side=tk.LEFT)
        combo = Combobox(theme_setting_frame, state="readonly", width=10, font=("微软雅黑", -24))
        combo.pack(side=tk.LEFT)
        return combo

    def __set_maximize_checkbutton(self) -> Checkbutton:
        check_btn = Checkbutton(self, text="  启动时最大化窗口")
        check_btn.grid(row=2, column=1, columnspan=2, pady=20, padx=(40, 30), sticky=tk.EW)
        return check_btn

    def __set_check_update_btn(self) -> Button:
        check_update_btn = Button(self, text="检查更新", takefocus=True, style=LINK, cursor="hand2")
        check_update_btn.grid(row=3, column=1, pady=20, padx=30, sticky=tk.W)
        return check_update_btn

    def __set_open_settings_file_btn(self) -> Button:
        open_settings_file_btn = Button(self, text="配置文件", takefocus=True, style=LINK, cursor="hand2")
        open_settings_file_btn.grid(row=3, column=2, pady=20, padx=30)
        return open_settings_file_btn

    def destroy(self) -> None:
        Publisher.unsubscribe(str(self.theme_combobox))
        super().destroy()
