from __future__ import annotations

import tkinter as tk
from ttkbootstrap import Menu

from config.settings import TkS


class ClickMenuView:
    parent: tk.Misc
    preview_setting_menu: Menu
    model_menu: Menu
    single_file_menu: Menu
    multi_file_menu: Menu
    __slots__ = (
        "parent", "preview_setting_menu", "model_menu",
        "single_file_menu", "multi_file_menu",
    )

    def __init__(self, parent: tk.Misc) -> None:
        self.parent = parent
        self.preview_setting_menu, self.model_menu = self.__set_preview_setting_menu()
        self.single_file_menu = self.__set_single_file_menu()
        self.multi_file_menu = self.__set_multi_file_menu()

    def __set_preview_setting_menu(self) -> tuple[Menu, Menu]:
        menu = Menu(self.parent, tearoff=0, activeborderwidth=TkS(3))
        menu.add_command(label="详情模式")
        menu.add_command(label="中等图标")
        menu.add_command(label="大图标")
        menu.add_command(label="超大图标")
        menu.add_separator()
        menu.add_command(label="结果数: 10")
        menu.add_command(label="结果数: 30")
        menu.add_command(label="结果数: 50")
        menu.add_command(label="结果数: 100")
        menu.add_separator()
        model_menu = Menu(self.parent, tearoff=0)
        menu.add_cascade(label="切换模型", menu=model_menu)
        return menu, model_menu

    def __set_single_file_menu(self) -> Menu:
        menu = Menu(self.parent, tearoff=0, activeborderwidth=TkS(3))
        menu.add_command(label="复制图片")
        menu.add_command(label="复制路径")
        menu.add_command(label="图片另存为")
        menu.add_command(label="删除图片")
        menu.add_separator()
        menu.add_command(label="打开图片")
        menu.add_command(label="打开文件夹")
        return menu

    def __set_multi_file_menu(self) -> Menu:
        menu = Menu(self.parent, tearoff=0, activeborderwidth=TkS(3))
        menu.add_command(label="复制图片")
        menu.add_command(label="复制路径")
        menu.add_command(label="图片另存为")
        menu.add_command(label="删除图片")
        return menu
