from __future__ import annotations

import tkinter as tk

from ttkbootstrap import Menu

from config.settings import TkS
from utils.i18n import _


class ClickMenuView:
    parent: tk.Misc
    __slots__ = ("parent", )

    def __init__(self, parent: tk.Misc) -> None:
        self.parent = parent

    @property
    def preview_setting_menu(self) -> tuple[Menu, Menu]:
        return self.__set_preview_setting_menu(self.parent)
    
    @property
    def single_file_menu(self) -> Menu:
        return self.__set_single_file_menu(self.parent)
    
    @property
    def multi_file_menu(self) -> Menu:
        return self.__set_multi_file_menu(self.parent)

    def __set_preview_setting_menu(self, parent) -> tuple[Menu, Menu]:
        menu = Menu(parent, tearoff=0, activeborderwidth=TkS(3))
        for preview_mode in (_("详情模式"), _("中等图标"), _("大图标"), _("超大图标")):
            menu.add_command(label=preview_mode)
        menu.add_separator()
        for count in (10, 30, 50, 100):
            menu.add_command(label=_("结果数: {count}", count=count))
        menu.add_separator()
        model_menu = Menu(parent, tearoff=0)
        menu.add_cascade(label=_("切换模型"), menu=model_menu)
        return menu, model_menu

    def __set_single_file_menu(self, parent) -> Menu:
        menu = Menu(parent, tearoff=0, activeborderwidth=TkS(3))
        menu.add_command(label=_("复制图片"))
        menu.add_command(label=_("复制路径"))
        menu.add_command(label=_("图片另存为"))
        menu.add_command(label=_("删除图片"))
        menu.add_separator()
        menu.add_command(label=_("打开图片"))
        menu.add_command(label=_("打开文件夹"))
        return menu

    def __set_multi_file_menu(self, parent) -> Menu:
        menu = Menu(parent, tearoff=0, activeborderwidth=TkS(3))
        menu.add_command(label=_("复制图片"))
        menu.add_command(label=_("复制路径"))
        menu.add_command(label=_("图片另存为"))
        menu.add_command(label=_("删除图片"))
        return menu
