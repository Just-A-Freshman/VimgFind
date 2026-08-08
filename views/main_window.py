from __future__ import annotations

import tkinter as tk

from tkinterdnd2 import TkinterDnD
from ttkbootstrap.constants import LINK
from ttkbootstrap.utility import enable_high_dpi_awareness
from ttkbootstrap import Button, Notebook, Window

from .index_page import IndexFrame
from .model_page import ModelFrame
from .search_page import SearchFrame
from config.settings import WinInfo
from utils.i18n import _


class WinGUI(Window, TkinterDnD.Tk):
    search_tab: SearchFrame
    index_tab: IndexFrame
    model_tab: ModelFrame
    switch_tab: Notebook
    common_setting_btn: Button
    __slots__ = ("search_tab", "index_tab", "model_tab", "switch_tab", "common_setting_btn")

    def __init__(self, full_screen: bool = False, topmost: bool = False) -> None:
        enable_high_dpi_awareness()
        super().__init__(iconphoto=None)
        self.__win(full_screen, topmost)
        self.switch_tab = self.__set_notebook(self)

    def __win(self, full_screen: bool, topmost: bool) -> None:
        self.title(WinInfo.title)
        if topmost:
            self.attributes("-topmost", True)
        screenwidth = self.winfo_screenwidth()
        screenheight = self.winfo_screenheight()
        width = WinInfo.width
        height = WinInfo.height
        geometry = '%dx%d+%d+%d' % (width, height, (screenwidth - width) // 2, (screenheight - height) // 2)
        self.geometry(geometry)
        if full_screen:
            self.attributes("-fullscreen", True)
            self.bind_all("<Escape>", lambda e: self.attributes("-fullscreen", False))
        WinInfo.set_window_icon(self)
        self.option_add('*Font', WinInfo.default_font)

    def __set_notebook(self, parent) -> Notebook:
        notebook = Notebook(parent)
        self.search_tab = SearchFrame(notebook)
        notebook.add(self.search_tab, text=_("  检索  "))
        self.index_tab = IndexFrame(notebook)
        notebook.add(self.index_tab, text=_("  索引  "))
        self.model_tab = ModelFrame(notebook)
        notebook.add(self.model_tab, text=_("  模型  "))
        notebook.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.common_setting_btn = Button(parent, text=_("通用设置"), style=LINK, cursor="hand2", takefocus=False, padding=(3, 0))
        self.common_setting_btn.place(relx=1.0, x=-2, y=0, anchor=tk.NE)
        return notebook
