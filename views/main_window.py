from tkinter.ttk import Notebook
from tkinterdnd2 import TkinterDnD
from ctypes import windll

from settings import WinInfo
from .search_page import SearchFrame
from .settings_page import SettingFrame
from .model_page import ModelFrame


class WinGUI(TkinterDnD.Tk):
    search_tab: SearchFrame
    setting_tab: SettingFrame
    model_tab: ModelFrame
    switch_tab: Notebook

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
        width = WinInfo.TkS(WinInfo.width)
        height = WinInfo.TkS(WinInfo.height)
        geometry = '%dx%d+%d+%d' % (width, height, (screenwidth - width) // 2, (screenheight - height) // 2)
        self.geometry(geometry)
        self.iconbitmap(WinInfo.ico_path)

    def __set_notebook(self, parent) -> Notebook:
        notebook = Notebook(parent)
        self.search_tab = SearchFrame(notebook)
        notebook.add(self.search_tab, text="  检索  ")
        self.setting_tab = SettingFrame(notebook)
        notebook.add(self.setting_tab, text="  设置  ")
        self.model_tab = ModelFrame(notebook)
        notebook.add(self.model_tab, text="  模型  ")
        notebook.place(relx=0, rely=0, relwidth=1, relheight=1)
        return notebook
