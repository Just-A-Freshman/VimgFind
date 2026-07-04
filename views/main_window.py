from tkinterdnd2 import TkinterDnD
from ttkbootstrap import Button, Notebook
from ttkbootstrap.constants import LINK
from ttkbootstrap.utility import enable_high_dpi_awareness
import tkinter as tk

from settings import WinInfo, TkS
from .search_page import SearchFrame
from .index_page import IndexFrame
from .model_page import ModelFrame


class WinGUI(TkinterDnD.Tk):
    search_tab: SearchFrame
    index_tab: IndexFrame
    model_tab: ModelFrame
    switch_tab: Notebook
    common_setting_btn: Button

    def __init__(self, full_screen: bool = False) -> None:
        enable_high_dpi_awareness()
        super().__init__()
        self.__win(full_screen)
        self.switch_tab = self.__set_notebook(self)

    def __win(self, full_screen) -> None:
        self.title(WinInfo.title)
        if full_screen:
            self.state("zoom")
        screenwidth = self.winfo_screenwidth()
        screenheight = self.winfo_screenheight()
        width = WinInfo.width
        height = WinInfo.height
        geometry = '%dx%d+%d+%d' % (width, height, (screenwidth - width) // 2, (screenheight - height) // 2)
        self.geometry(geometry)
        self.iconbitmap(WinInfo.ico_path)
        self.option_add("*TCombobox*Listbox.font", (WinInfo.default_font_family, WinInfo.default_font_size))
        self.option_add('*Menu.font', (WinInfo.default_font_family, WinInfo.default_font_size))

    def __set_notebook(self, parent) -> Notebook:
        notebook = Notebook(parent)
        self.search_tab = SearchFrame(notebook)
        notebook.add(self.search_tab, text="  检索  ")
        self.index_tab = IndexFrame(notebook)
        notebook.add(self.index_tab, text="  索引  ")
        self.model_tab = ModelFrame(notebook)
        notebook.add(self.model_tab, text="  模型  ")
        notebook.place(relx=0, rely=0, relwidth=1, relheight=1)

        self.common_setting_btn = Button(parent, text="通用设置", style=LINK, cursor="hand2")
        self.common_setting_btn.place(relx=1.0, x=TkS(-2), y=WinInfo.PX_1, anchor=tk.NE)
        return notebook
