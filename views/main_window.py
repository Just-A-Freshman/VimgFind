from tkinter.ttk import Notebook
from tkinterdnd2 import TkinterDnD
from ttkbootstrap import Button
from ttkbootstrap.constants import LINK
from ctypes import windll
import tkinter as tk

from settings import WinInfo
from .search_page import SearchFrame
from .index_page import IndexFrame
from .model_page import ModelFrame


class WinGUI(TkinterDnD.Tk):
    search_tab: SearchFrame
    index_tab: IndexFrame
    model_tab: ModelFrame
    switch_tab: Notebook
    common_setting_btn: Button

    def __init__(self) -> None:
        self._set_dpi_awareness()
        super().__init__()
        self.__win()
        self.switch_tab = self.__set_notebook(self)

    def _set_dpi_awareness(self) -> None:
        try:
            windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                windll.shcore.SetProcessDpiAwareness(1)
            except Exception:
                pass

    def __win(self) -> None:
        self.title(WinInfo.title)
        screenwidth = self.winfo_screenwidth()
        screenheight = self.winfo_screenheight()
        width = WinInfo.width
        height = WinInfo.height
        geometry = '%dx%d+%d+%d' % (width, height, (screenwidth - width) // 2, (screenheight - height) // 2)
        self.geometry(geometry)
        self.iconbitmap(WinInfo.ico_path)
        self.option_add("*TCombobox*Listbox.font", ("微软雅黑", -24))

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
        self.common_setting_btn.place(relx=1.0, x=-5, y=3, anchor=tk.NE)
        return notebook
