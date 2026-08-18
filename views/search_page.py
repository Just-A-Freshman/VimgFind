from __future__ import annotations

import tkinter as tk

from ttkbootstrap import Button, Entry, Checkbutton, Scale, Frame, Label, Labelframe, Combobox, Scrollbar

from .widgets import BasicImagePreviewView, PreviewCanvasView
from config.settings import TkS, Setting
from utils.i18n import _


class FilterPanel(Labelframe):
    sim_scale: Scale
    sim_value: Label
    ext_combo: Combobox
    size_min: Entry
    size_max: Entry
    size_min_unit: Combobox
    size_max_unit: Combobox
    folder_select_all: Checkbutton
    dedup_check: Checkbutton
    folder_listbox: tk.Listbox
    confirm_btn: Button
    cancel_btn: Button
    __slots__ = (
        "sim_scale", "sim_value", "ext_combo",
        "size_min", "size_min_unit", "size_max", "size_max_unit",
        "folder_select_all", "dedup_check", "folder_listbox",
        "confirm_btn", "cancel_btn",
    )

    def __init__(self, parent, **kwargs) -> None:
        super().__init__(parent, text=_("过滤设置"), **kwargs)
        self.place_forget()
        self._setup_grid()

        self.sim_scale, self.sim_value = self.__set_sim_scale()
        self.ext_combo = self.__set_ext_combo()
        self.size_min, self.size_min_unit = self.__set_size_min()
        self.size_max, self.size_max_unit = self.__set_size_max()
        folder_left_frame = self.__set_folder_left_frame()
        self.folder_select_all = self.__set_folder_select_all(folder_left_frame)
        self.dedup_check = self.__set_dedup_check(folder_left_frame)
        self.folder_listbox = self.__set_folder_listbox()
        self.confirm_btn, self.cancel_btn = self.__set_confirm_cancel_btn()

    def _setup_grid(self) -> None:
        for col, weight in enumerate([0, 1, 0, 0, 1, 0, 0]):
            self.grid_columnconfigure(col, weight=weight)
        self.grid_columnconfigure(6, minsize=TkS(6))

    def __set_sim_scale(self) -> tuple[Scale, Label]:
        label = Label(self, text=_("相似度阈值"), width=10, anchor=tk.W)
        label.grid(row=0, column=0, sticky=tk.W, padx=(TkS(6), 0), pady=(TkS(10), TkS(5)))
        sim_scale = Scale(self, from_=0, to=100, orient=tk.HORIZONTAL)
        sim_value = Label(self, text="0%", width=5)
        sim_scale.grid(row=0, column=1, columnspan=4, sticky=tk.EW, padx=(TkS(4), TkS(2)), pady=(TkS(10), TkS(5)))
        sim_value.grid(row=0, column=5, sticky=tk.E, pady=(TkS(10), TkS(5)))
        return sim_scale, sim_value

    def __set_ext_combo(self) -> Combobox:
        label = Label(self, text=_("文件类型"), width=10, anchor=tk.W)
        label.grid(row=1, column=0, sticky=tk.W, padx=(TkS(6), 0), pady=(TkS(5), TkS(5)))
        ext_combo = Combobox(self, values=[_("所有图片文件"), *Setting.ext_group_map], state="readonly")
        ext_combo.grid(row=1, column=1, columnspan=5, sticky=tk.EW, padx=(TkS(4), 0), pady=(TkS(5), TkS(5)))
        ext_combo.current(0)
        return ext_combo

    def __set_size_unit_combo(self, column: int, padx: tuple) -> Combobox:
        combo = Combobox(self, values=["KB", "MB"], state="readonly", width=4)
        combo.grid(row=2, column=column, sticky=tk.EW, padx=padx, pady=(TkS(5), TkS(5)))
        combo.current(1)
        return combo

    def __set_size_min(self) -> tuple[Entry, Combobox]:
        label = Label(self, text=_("文件大小"), width=10, anchor=tk.W)
        label.grid(row=2, column=0, sticky=tk.W, padx=(TkS(6), 0), pady=(TkS(5), TkS(5)))
        size_min = Entry(self, width=6)
        size_min.grid(row=2, column=1, sticky=tk.EW, padx=(TkS(4), TkS(1)), pady=(TkS(5), TkS(5)))
        size_min_unit = self.__set_size_unit_combo(2, (0, TkS(1)))
        return size_min, size_min_unit

    def __set_size_max(self) -> tuple[Entry, Combobox]:
        Label(self, text=_("到")).grid(row=2, column=3, pady=(TkS(5), TkS(5)))
        size_max = Entry(self, width=6)
        size_max.grid(row=2, column=4, sticky=tk.EW, padx=(TkS(2), TkS(1)), pady=(TkS(5), TkS(5)))
        size_max_unit = self.__set_size_unit_combo(5, (0, 0))
        return size_max, size_max_unit

    def __set_folder_left_frame(self) -> Frame:
        left_frame = Frame(self)
        Label(left_frame, text=_("所属文件夹"), width=10, anchor=tk.W).pack(anchor=tk.W)
        left_frame.grid(row=3, column=0, sticky=tk.NW, padx=(TkS(6), 0), pady=(TkS(5), TkS(1)))
        return left_frame

    def __set_folder_select_all(self, parent: Frame) -> Checkbutton:
        folder_select_all = Checkbutton(parent, text=_("全选"), cursor="hand2")
        folder_select_all.pack(anchor=tk.W, pady=(TkS(11), 0))
        return folder_select_all

    def __set_dedup_check(self, parent: Frame) -> Checkbutton:
        dedup_check = Checkbutton(parent, text=_("去重"), cursor="hand2")
        dedup_check.pack(anchor=tk.W, pady=(TkS(8), 0))
        return dedup_check

    def __set_folder_listbox(self) -> tk.Listbox:
        lbox_frame = Frame(self)
        lbox_frame.grid(row=3, column=1, columnspan=5, sticky=tk.N+tk.E+tk.W, padx=(TkS(4), 0), pady=(TkS(5), TkS(1)))
        lbox_frame.grid_columnconfigure(0, weight=1)
        lbox_frame.grid_rowconfigure(0, weight=1)
        folder_listbox = tk.Listbox(
            lbox_frame, selectmode=tk.MULTIPLE, height=5, width=1,
            activestyle='none', exportselection=False, justify=tk.LEFT
        )
        folder_listbox.grid(row=0, column=0, sticky=tk.EW)
        h_scroll = Scrollbar(lbox_frame, orient=tk.HORIZONTAL, command=folder_listbox.xview)
        h_scroll.grid(row=1, column=0, sticky=tk.EW)
        folder_listbox.configure(xscrollcommand=h_scroll.set)
        return folder_listbox

    def __set_confirm_cancel_btn(self) -> tuple[Button, Button]:
        btn_frame = Frame(self)
        btn_frame.grid(row=4, column=0, columnspan=7, pady=(TkS(7), TkS(15)))
        confirm_btn = Button(btn_frame, text=_("确定"), takefocus=False, cursor="hand2", padding=(TkS(10), TkS(4)))
        confirm_btn.grid(row=0, column=0, padx=(0, TkS(25)))
        cancel_btn = Button(btn_frame, text=_("取消"), takefocus=False, cursor="hand2", padding=(TkS(10), TkS(4)), style="secondary")
        cancel_btn.grid(row=0, column=1)
        return confirm_btn, cancel_btn


class SearchFrame(Frame):
    search_entry: Entry
    filter_btn: tk.Label
    search_by_browser_btn: Button
    search_by_clipboard_btn: Button
    more_options_button: Button
    filter_panel: FilterPanel
    preview_container: Frame
    preview_view: BasicImagePreviewView
    preview_frame1: Labelframe
    preview_frame2: Labelframe
    preview_canvas1: PreviewCanvasView
    preview_canvas2: PreviewCanvasView
    nav_frame: tk.Frame
    nav_prev: Button
    nav_next: Button
    nav_page_label: Label
    toast_label: Label
    __slots__ = (
        "search_entry", "filter_btn",
        "search_by_browser_btn", "search_by_clipboard_btn",
        "more_options_button", "filter_panel",
        "preview_container", "preview_view",
        "preview_frame1", "preview_frame2",
        "preview_canvas1", "preview_canvas2",
        "nav_frame", "nav_prev", "nav_next",
        "nav_page_label", "toast_label",
    )

    def __init__(self, parent, **kwargs) -> None:
        super().__init__(parent, **kwargs)
        self.pack(fill=tk.BOTH, expand=True)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=32, uniform="main_col", minsize=TkS(200))
        self.grid_columnconfigure(1, weight=19, uniform="main_col", minsize=TkS(150))

        left_panel = self.__set_left_panel()
        self.search_entry = self.__set_search_entry(left_panel)
        self.filter_btn = self.__set_filter_btn()
        self.search_by_clipboard_btn = self.__set_search_by_clipboard_button(left_panel)
        self.search_by_browser_btn = self.__set_search_by_browser_button(left_panel)
        self.more_options_button = self.__set_more_options_button()
        self.filter_panel = FilterPanel(self)
        self.preview_container = self.__set_preview_results_frame()
        self.preview_view = BasicImagePreviewView(self.preview_container)
        right_panel = self.__set_right_panel()
        self.preview_frame1 = self.__set_preview_frame1(right_panel)
        self.preview_frame2 = self.__set_preview_frame2(right_panel)
        self.preview_canvas1 = PreviewCanvasView(self.preview_frame1)
        self.preview_canvas2 = PreviewCanvasView(self.preview_frame2)
        self.toast_label = Label(self.preview_container, padding=TkS(5), style="inverse-success")
        self.nav_frame, self.nav_page_label, self.nav_prev, self.nav_next = self.__set_nav_buttons()

    def __set_left_panel(self) -> Frame:
        frame = Frame(self)
        frame.grid(row=0, column=0, sticky=tk.EW, padx=(TkS(5), 0), pady=(TkS(3), 0))
        return frame

    def __set_search_entry(self, parent) -> Entry:
        ipt = Entry(parent)
        ipt.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=TkS(7), pady=(TkS(5), 0))
        return ipt

    def __set_filter_btn(self) -> tk.Label:
        btn = tk.Label(self, text="▼", cursor="hand2", bd=0, highlightthickness=0, relief=tk.FLAT)
        btn.pack(in_=self.search_entry, side=tk.RIGHT, fill=tk.Y, ipadx=TkS(6), pady=TkS(2), padx=TkS(2))
        return btn

    def __set_search_by_browser_button(self, parent) -> Button:
        btn = Button(parent, text=_("浏览"), takefocus=False, width=9)
        btn.pack(side=tk.RIGHT, ipady=TkS(5.5), padx=TkS(6), pady=(TkS(5), 0))
        return btn

    def __set_search_by_clipboard_button(self, parent) -> Button:
        btn = Button(parent, text=_("剪切板"), takefocus=False, width=9)
        btn.pack(side=tk.RIGHT, ipady=TkS(5.5), padx=(0, TkS(2)), pady=(TkS(5), 0))
        return btn
    
    def __set_right_panel(self) -> Frame:
        frame = Frame(self)
        frame.grid(row=1, column=1, sticky=tk.NSEW, padx=(TkS(2), TkS(5)), pady=(0, TkS(5)))
        frame.grid_rowconfigure(0, weight=1, uniform="right_row")
        frame.grid_rowconfigure(1, weight=1, uniform="right_row")
        frame.grid_columnconfigure(0, weight=1)
        return frame

    def __set_more_options_button(self) -> Button:
        button = Button(self, text="• • •", takefocus=False, style="link", cursor="hand2")
        button.grid(row=0, column=1, sticky=tk.E, padx=(0, TkS(5)))
        return button

    def __set_preview_results_frame(self) -> Frame:
        frame = Frame(self)
        frame.grid(row=1, column=0, sticky=tk.NSEW, padx=(TkS(5), TkS(2)), pady=(TkS(9), TkS(5)))
        return frame

    def __set_preview_frame1(self, parent) -> Labelframe:
        frame = Labelframe(parent, text=_("源图片"))
        frame.grid(row=0, column=0, sticky=tk.NSEW, pady=(0, TkS(2)))
        return frame

    def __set_preview_frame2(self, parent) -> Labelframe:
        frame = Labelframe(parent, text=_("匹配图片"))
        frame.grid(row=1, column=0, sticky=tk.NSEW, pady=(TkS(2), 0))
        return frame

    def __set_nav_buttons(self) -> tuple[tk.Frame, Label, Button, Button]:
        nav_frame = tk.Frame(self.preview_container, borderwidth=0)
        nav_page_label = Label(nav_frame, text="0 / 0")
        nav_page_label.pack(side=tk.LEFT, padx=(TkS(15), 0), pady=(TkS(7), TkS(2)))
        nav_prev = Button(
            nav_frame, text="◀", takefocus=False,
            cursor="hand2", padding=(TkS(4), TkS(1)), width=3
        )
        nav_next = Button(
            nav_frame, text="▶", takefocus=False,
            cursor="hand2", padding=(TkS(4), TkS(1)), width=3
        )
        nav_next.pack(side=tk.RIGHT, padx=(0, TkS(5)), pady=(TkS(7), TkS(2)))
        nav_prev.pack(side=tk.RIGHT, padx=(0, TkS(5)), pady=(TkS(7), TkS(2)))
        nav_frame.pack_forget()
        return nav_frame, nav_page_label, nav_prev, nav_next

    def set_nav_visible(self, show: bool) -> None:
        if show:
            self.nav_frame.grid(row=1, column=0, sticky='ew', padx=(TkS(1), TkS(12)), pady=(0, TkS(1)))
            self.nav_frame.lift()
        else:
            self.nav_frame.grid_forget()

    def set_nav_state(self, current_page: int, total_page: int) -> None:
        self.nav_page_label.config(text=f"{current_page} / {total_page}")
        self.nav_prev.config(state=tk.NORMAL if current_page > 1 else tk.DISABLED)
        self.nav_next.config(state=tk.NORMAL if current_page < total_page else tk.DISABLED)
