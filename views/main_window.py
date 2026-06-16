from tkinter.ttk import Notebook
from tkinterdnd2 import TkinterDnD
from ctypes import windll

from config import WinInfo
from .search_page import SearchFrame
from .settings_page import SettingFrame


class WinGUI(TkinterDnD.Tk):
    search_tab: SearchFrame
    setting_tab: SettingFrame
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
        hegiht = WinInfo.TkS(WinInfo.height)
        geometry = '%dx%d+%d+%d' % (width, hegiht, (screenwidth - width) // 2, (screenheight - hegiht) // 2)
        self.geometry(geometry)
        self.iconbitmap(WinInfo.ico_path)

    def __set_notebook(self, parent) -> Notebook:
        notebook = Notebook(parent)
        self.search_tab = SearchFrame(notebook)
        notebook.add(self.search_tab, text="  检索  ")
        self.setting_tab = SettingFrame(notebook)
        notebook.add(self.setting_tab, text="  设置  ")
        notebook.place(relx=0, rely=0, relwidth=1, relheight=1)
        return notebook
