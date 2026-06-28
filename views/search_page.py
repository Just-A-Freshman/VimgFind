from ttkbootstrap import Button, Entry, Checkbutton, Scale
from tkinter.ttk import Frame, Label, LabelFrame, Combobox, Scrollbar
import tkinter as tk

from settings import WinInfo
from .widgets import BasicImagePreviewView, PreviewCanvasView


class FilterPanel(LabelFrame):
    sim_scale: Scale
    sim_value: Label
    ext_combo: Combobox
    size_min: Entry
    size_max: Entry
    size_min_unit: Combobox
    size_max_unit: Combobox
    folder_select_all: Checkbutton
    folder_listbox: tk.Listbox
    confirm_btn: Button
    cancel_btn: Button

    def __init__(self, parent, **kwargs) -> None:
        super().__init__(parent, text="过滤设置", **kwargs)
        self.place_forget()
        self._build()

    def _build(self) -> None:
        for col, weight in enumerate([0, 1, 0, 0, 1, 0, 0]):
            self.grid_columnconfigure(col, weight=weight)
        self.grid_columnconfigure(6, minsize=12)

        # 第 0 行：相似度阈值
        Label(self, text="相似度阈值", width=10, anchor=tk.W).grid(
            row=0, column=0, sticky=tk.W, padx=(12, 0), pady=(20, 10)
        )
        self.sim_scale = Scale(self, from_=0, to=100, orient=tk.HORIZONTAL)
        self.sim_scale.grid(row=0, column=1, columnspan=4, sticky=tk.EW, padx=(8, 4), pady=(20, 10))
        self.sim_value = Label(self, text="0%", width=5)
        self.sim_value.grid(row=0, column=5, sticky=tk.E, pady=(20, 10))

        # 第 1 行：文件类型
        Label(self, text="文件类型", width=10, anchor=tk.W).grid(
            row=1, column=0, sticky=tk.W, padx=(12, 0), pady=(10, 10)
        )
        self.ext_combo = Combobox(
            self,
            values=["所有图片文件", "PNG", "JPG/JPEG", "WebP", "GIF", "BMP", "TIFF"],
            state="readonly",
        )
        self.ext_combo.grid(row=1, column=1, columnspan=5, sticky=tk.EW, padx=(8, 0), pady=(10, 10))
        self.ext_combo.current(0)

        # 第 2 行：文件大小
        Label(self, text="文件大小", width=10, anchor=tk.W).grid(
            row=2, column=0, sticky=tk.W, padx=(12, 0), pady=(10, 10)
        )
        self.size_min = Entry(self, width=6)
        self.size_min.grid(row=2, column=1, sticky=tk.EW, padx=(8, 2), pady=(10, 10))
        self.size_min_unit = Combobox(self, values=["KB", "MB"], state="readonly", width=4)
        self.size_min_unit.grid(row=2, column=2, sticky=tk.EW, padx=(0, 4), pady=(10, 10))
        self.size_min_unit.current(1)
        Label(self, text="到").grid(row=2, column=3, pady=(10, 10))
        self.size_max = Entry(self, width=6)
        self.size_max.grid(row=2, column=4, sticky=tk.EW, padx=(4, 2), pady=(10, 10))
        self.size_max_unit = Combobox(self, values=["KB", "MB"], state="readonly", width=4)
        self.size_max_unit.grid(row=2, column=5, sticky=tk.EW, padx=(0, 0), pady=(10, 10))
        self.size_max_unit.current(1)

        # 第 3 行：所属文件夹标签 + 全选 + 多选列表
        left_frame = Frame(self)
        left_frame.grid(row=3, column=0, sticky=tk.NW, padx=(12, 0), pady=(10, 2))
        Label(left_frame, text="所属文件夹", width=10, anchor=tk.W).pack(anchor=tk.W)
        self.folder_select_all = Checkbutton(left_frame, text="全选", style="square-toggle")
        self.folder_select_all.pack(anchor=tk.W, pady=(22, 0))

        lbox_frame = Frame(self)
        lbox_frame.grid(
            row=3, column=1, columnspan=5, sticky=tk.N+tk.E+tk.W,
            padx=(8, 0), pady=(10, 2)
        )
        lbox_frame.grid_columnconfigure(0, weight=1)
        lbox_frame.grid_rowconfigure(0, weight=1)
        self.folder_listbox = tk.Listbox(
            lbox_frame, selectmode=tk.MULTIPLE,
            height=5, width=1, activestyle='none',
            exportselection=False, justify=tk.LEFT
        )
        self.folder_listbox.grid(row=0, column=0, sticky=tk.EW)
        folder_scroll_h = Scrollbar(lbox_frame, orient=tk.HORIZONTAL, command=self.folder_listbox.xview)
        folder_scroll_h.grid(row=1, column=0, sticky=tk.EW)
        self.folder_listbox.configure(xscrollcommand=folder_scroll_h.set)

        # 底部按钮
        btn_frame = Frame(self)
        btn_frame.grid(row=4, column=0, columnspan=7, pady=(14, 30))
        btn_center = Frame(btn_frame)
        btn_center.pack(anchor=tk.CENTER)
        self.confirm_btn = Button(btn_center, text="确定", takefocus=False, cursor="hand2", padding=(20, 8))
        self.confirm_btn.pack(side=tk.LEFT, padx=(0, 50))
        self.cancel_btn = Button(btn_center, text="取消", takefocus=False, cursor="hand2", padding=(20, 8), style="secondary")
        self.cancel_btn.pack(side=tk.LEFT)


class SearchFrame(Frame):
    search_entry: Entry
    filter_btn: tk.Label
    search_by_browser_btn: Button
    search_by_clipboard_btn: Button
    more_options_button: Button
    filter_panel: FilterPanel
    preview_container: Frame
    preview_view: BasicImagePreviewView
    preview_frame1: LabelFrame
    preview_frame2: LabelFrame
    preview_canvas1: PreviewCanvasView
    preview_canvas2: PreviewCanvasView
    nav_frame: Frame
    nav_prev: Button
    nav_next: Button

    def __init__(self, parent, **kwargs) -> None:
        super().__init__(parent, **kwargs)
        self.place(relx=0, rely=0, relwidth=1, relheight=1)

        self.search_entry = self.__set_search_entry()
        self.filter_btn = self.__set_filter_btn()
        self.search_by_browser_btn = self.__set_search_by_browser_button()
        self.search_by_clipboard_btn = self.__set_search_by_clipboard_button()
        self.more_options_button = self.__set_more_options_button()
        self.filter_panel = FilterPanel(self)
        self.preview_container = self.__set_preview_results_frame()
        self.preview_view = BasicImagePreviewView(self.preview_container)
        self.preview_frame1 = self.__set_preview_frame1()
        self.preview_frame2 = self.__set_preview_frame2()
        self.preview_canvas1 = PreviewCanvasView(self.preview_frame1)
        self.preview_canvas2 = PreviewCanvasView(self.preview_frame2)
        self.__set_nav_buttons()

    def __set_search_entry(self) -> Entry:
        ipt = Entry(self)
        ipt.place(relx=0.01, rely=0.02, relwidth=0.395, relheight=0.0690)
        return ipt

    def __set_filter_btn(self) -> tk.Label:
        btn = tk.Label(self, text="▼", cursor="hand2", bd=0, highlightthickness=0, relief=tk.FLAT)
        btn.place(
            in_=self.search_entry, relx=1.0, rely=0.1, anchor=tk.NE,
            x=WinInfo.TkS(-3), y=WinInfo.TkS(3),
            width=WinInfo.TkS(28), height=WinInfo.TkS(26)
        )
        return btn

    def __set_search_by_browser_button(self) -> Button:
        btn = Button(self, text="浏览", takefocus=False)
        btn.place(relx=0.415, rely=0.0192, relwidth=0.1, relheight=0.0690)
        return btn

    def __set_search_by_clipboard_button(self) -> Button:
        btn = Button(self, text="剪切板", takefocus=False)
        btn.place(relx=0.525, rely=0.0192, relwidth=0.1, relheight=0.0690)
        return btn

    def __set_more_options_button(self) -> Button:
        button = Button(self, text="• • •", takefocus=False, style="link", cursor="hand2")
        button.place(relx=1, rely=0.0192, width=WinInfo.TkS(50), x=WinInfo.TkS(-50))
        return button

    def __set_preview_results_frame(self) -> Frame:
        frame = Frame(self)
        frame.place(relx=0.01, rely=0.1111, relwidth=0.6170, relheight=0.888)
        return frame

    def __set_preview_frame1(self) -> LabelFrame:
        frame = LabelFrame(self, text="源图片")
        frame.place(relx=0.63, rely=0.095, relwidth=0.365, relheight=0.4444)
        return frame

    def __set_preview_frame2(self) -> LabelFrame:
        frame = LabelFrame(self, text="匹配图片")
        frame.place(relx=0.63, rely=0.5555, relwidth=0.365, relheight=0.4444)
        return frame

    def __set_nav_buttons(self) -> None:
        self.nav_frame = Frame(self.preview_container)
        self.nav_prev = Button(
            self.nav_frame, text="◀", takefocus=False,
            cursor="hand2", padding=(8, 2), width=3
        )
        self.nav_prev.pack(side=tk.LEFT, padx=(0, 4))
        self.nav_next = Button(
            self.nav_frame, text="▶", takefocus=False,
            cursor="hand2", padding=(8, 2), width=3
        )
        self.nav_next.pack(side=tk.LEFT)
        self.nav_frame.place(relx=1.0, rely=1.0, anchor=tk.SE, x=WinInfo.TkS(-10), y=WinInfo.TkS(-10))
        self.nav_frame.place_forget()

    def set_nav_visible(self, show: bool) -> None:
        if show:
            self.nav_frame.place(relx=0.99, rely=1.0, anchor=tk.SE, x=WinInfo.TkS(-8), y=WinInfo.TkS(-1))
            self.nav_frame.lift()
        else:
            self.nav_frame.place_forget()

    def set_nav_state(self, has_prev: bool, has_next: bool) -> None:
        self.nav_prev.config(state=tk.NORMAL if has_prev else tk.DISABLED)
        self.nav_next.config(state=tk.NORMAL if has_next else tk.DISABLED)
