from ttkbootstrap import Button, Entry, Checkbutton, Scale, Style
from ttkbootstrap.constants import LINK
from tkinter.ttk import (
    Notebook, Frame, Treeview, Label, LabelFrame, Combobox
)
from tkinterdnd2 import TkinterDnD
import tkinter as tk
from ctypes import windll


from setting import WinInfo
from widgets import BasicImagePreviewView, PreviewCanvasView



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
        # Grid 列配置（用于跨行对齐）
        # Col 0: 标签(width=10) | Col 1: 左侧输入区(expand) | Col 2: 第一单位下拉框
        # Col 3: "到"分隔符 | Col 4: 右侧输入区(expand) | Col 5: 第二单位下拉框
        # Col 6: 尾部(expand)
        for col, weight in enumerate([0, 1, 0, 0, 1, 0, 1]):
            self.grid_columnconfigure(col, weight=weight)

        # 第 0 行：相似度阈值
        Label(self, text="相似度阈值", width=10, anchor=tk.W).grid(
            row=0, column=0, sticky='w', padx=(12, 0), pady=(20, 10))
        self.sim_scale = Scale(self, from_=0, to=100, orient=tk.HORIZONTAL)
        self.sim_scale.grid(row=0, column=1, columnspan=4, sticky='ew',
                            padx=(8, 4), pady=(20, 10))
        self.sim_value = Label(self, text="0%", width=5)
        self.sim_value.grid(row=0, column=5, sticky='e', pady=(20, 10))

        # 第 1 行：文件类型
        Label(self, text="文件类型", width=10, anchor=tk.W).grid(
            row=1, column=0, sticky='w', padx=(12, 0), pady=(10, 10))
        self.ext_combo = Combobox(
            self,
            values=["所有图片文件", "PNG", "JPG/JPEG", "WebP", "GIF", "BMP", "TIFF"],
            state="readonly",
        )
        self.ext_combo.grid(row=1, column=1, columnspan=5, sticky='ew',
                            padx=(8, 4), pady=(10, 10))
        self.ext_combo.current(0)

        # 第 2 行：文件大小
        Label(self, text="文件大小", width=10, anchor=tk.W).grid(
            row=2, column=0, sticky='w', padx=(12, 0), pady=(10, 10))
        self.size_min = Entry(self, width=6)
        self.size_min.grid(row=2, column=1, sticky='ew', padx=(8, 2), pady=(10, 10))
        self.size_min_unit = Combobox(self, values=["KB", "MB"], state="readonly", width=4)
        self.size_min_unit.grid(row=2, column=2, sticky='ew', padx=(0, 4), pady=(10, 10))
        self.size_min_unit.current(1)
        Label(self, text="到").grid(row=2, column=3, pady=(10, 10))
        self.size_max = Entry(self, width=6)
        self.size_max.grid(row=2, column=4, sticky='ew', padx=(4, 2), pady=(10, 10))
        self.size_max_unit = Combobox(self, values=["KB", "MB"], state="readonly", width=4)
        self.size_max_unit.grid(row=2, column=5, sticky='ew', padx=(0, 2), pady=(10, 10))
        self.size_max_unit.current(1)

        # 第 3 行：所属文件夹标签 + 全选 + 多选列表
        left_frame = Frame(self)
        left_frame.grid(row=3, column=0, sticky='nw', padx=(12, 0), pady=(10, 2))
        Label(left_frame, text="所属文件夹", width=10, anchor=tk.W).pack(anchor=tk.W)
        self.folder_select_all = Checkbutton(left_frame, text="全选", style="square-toggle")
        self.folder_select_all.pack(anchor=tk.W, pady=(22, 0))

        lbox_frame = Frame(self)
        lbox_frame.grid(
            row=3, column=1, columnspan=5, sticky='new',
            padx=(8, 2), pady=(10, 2)
        )
        lbox_frame.grid_columnconfigure(0, weight=1)
        self.folder_listbox = tk.Listbox(lbox_frame, selectmode=tk.MULTIPLE,
                                          height=5, width=1, activestyle='none',
                                          exportselection=False, justify=tk.LEFT)
        self.folder_listbox.grid(row=0, column=0, sticky='ew')

        # 底部按钮
        btn_frame = Frame(self)
        btn_frame.grid(row=4, column=0, columnspan=7, pady=(14, 16))
        btn_center = Frame(btn_frame)
        btn_center.pack(anchor='center')
        self.confirm_btn = Button(btn_center, text="确定", takefocus=False, cursor="hand2", padding=(20, 8))
        self.confirm_btn.pack(side='left', padx=(0, 50))
        self.cancel_btn = Button(btn_center, text="取消", takefocus=False, cursor="hand2", padding=(20, 8), style="secondary")
        self.cancel_btn.pack(side='left')


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

    def __set_search_entry(self) -> Entry:
        ipt = Entry(self)
        ipt.place(relx=0.01, rely=0.02, relwidth=0.395, relheight=0.0690)
        return ipt

    def __set_filter_btn(self) -> tk.Label:
        btn = tk.Label(self, text="▼", cursor="hand2", bd=0, highlightthickness=0, relief=tk.FLAT)
        btn.place(in_=self.search_entry, relx=1.0, rely=0.1, anchor='ne',
                  x=WinInfo.TkS(-3), y=WinInfo.TkS(3),
                  width=WinInfo.TkS(28), height=WinInfo.TkS(26))
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
        button = Button(self, text="• • •", takefocus=False, style=LINK, cursor="hand2")
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


class SettingFrame(Frame):
    index_tip_label: Label
    index_dataset_table: Treeview
    index_setting_frame: LabelFrame
    common_setting_frame: LabelFrame
    add_index_button: Button
    update_index_button: Button
    delete_index_button: Button
    rebuild_index_button: Button
    theme_combobox: Combobox
    auto_update_btn: Checkbutton
    update_threads_count_scale: Scale
    open_setting_file_button: Button
    open_repertory_button: Button

    def __init__(self, parent, **kwargs) -> None:
        super().__init__(parent, **kwargs)
        self.place(relx=0, rely=0, relwidth=1, relheight=1)

        self.index_tip_label = self.__set_index_tip_label()
        self.index_dataset_table = self.__set_index_dataset_table()
        self.index_setting_frame = self.__set_index_setting_frame()
        self.common_setting_frame = self.__set_common_setting_frame()
        self.add_index_button = self.__set_add_index_button()
        self.update_index_button = self.__set_update_index_button()
        self.delete_index_button = self.__set_delete_index_button()
        self.rebuild_index_button = self.__set_rebuild_index_button()
        self.theme_combobox = self.__set_theme_combobox()
        self.auto_update_btn = self.__set_auto_update_checkbutton()
        self.update_threads_count_scale = self.__set_update_threads_count_scale()
        self.open_setting_file_button = self.__set_open_setting_btn()
        self.open_repertory_button = self.__set_open_open_repertory_btn()

    def __set_index_tip_label(self) -> Label:
        label = Label(self, text="当前索引的图库(~张图片)", anchor=tk.NW, font=("微软雅黑", 14))
        label.place(relx=0.0081, rely=0.04, relwidth=1, relheight=0.0575)
        return label

    def __set_index_dataset_table(self) -> Treeview:
        columns = [" ", "图库目录"]
        table = Treeview(self, show="headings", columns=columns)
        table.heading(0, text=columns[0], anchor=tk.CENTER)
        table.column(0, width=60, anchor=tk.CENTER, stretch=False)
        table.heading(1, text=columns[1], anchor=tk.CENTER)
        table.column(1, anchor=tk.CENTER)
        table.place(relx=0.0081, rely=0.1111, relwidth=0.7, relheight=0.888)
        return table

    def __set_index_setting_frame(self) -> LabelFrame:
        frame = LabelFrame(self, text="索引设置")
        frame.place(relx=0.7181, rely=0.095, relwidth=0.2719, relheight=0.4738)
        for i in range(4):
            frame.grid_rowconfigure(i, weight=1)
        frame.grid_columnconfigure(0, weight=1)
        return frame

    def __set_add_index_button(self) -> Button:
        btn = Button(self.index_setting_frame, text="添加索引目录", takefocus=False)
        btn.grid(row=0, column=0, padx=5, pady=(10, 5), ipadx=10, ipady=5, sticky=tk.NSEW)
        return btn

    def __set_update_index_button(self) -> Button:
        btn = Button(self.index_setting_frame, text="更新索引目录", takefocus=False)
        btn.grid(row=1, column=0, padx=5, pady=5, ipadx=10, ipady=5, sticky=tk.NSEW)
        return btn

    def __set_delete_index_button(self) -> Button:
        btn = Button(self.index_setting_frame, text="删除索引目录", takefocus=False)
        btn.grid(row=2, column=0, padx=5, pady=5, ipadx=10, ipady=5, sticky=tk.NSEW)
        return btn

    def __set_rebuild_index_button(self) -> Button:
        btn = Button(self.index_setting_frame, text="重建索引目录", takefocus=False)
        btn.grid(row=3, column=0, padx=5, pady=(5, 10), ipadx=10, ipady=5, sticky=tk.NSEW)
        return btn

    def __set_common_setting_frame(self) -> LabelFrame:
        frame = LabelFrame(self, text="通用设置")
        frame.place(relx=0.7181, rely=0.58, relwidth=0.2609 + 0.011, relheight=0.42)
        for i in range(5):
            frame.grid_rowconfigure(i, weight=1)
        frame.grid_columnconfigure(0, weight=1, uniform='space')
        frame.grid_columnconfigure(1, weight=1, uniform='labels')
        frame.grid_columnconfigure(2, weight=1, uniform='controls')
        frame.grid_columnconfigure(3, weight=1, uniform='space')
        return frame

    def __set_theme_combobox(self) -> Combobox:
        style = Style()
        theme_names = style.theme_names()
        tip = Label(self.common_setting_frame, text="界面主题设置")
        tip.grid(row=1, column=1, padx=(5, 10), sticky=tk.E)
        comb = Combobox(self.common_setting_frame, values=theme_names, state="readonly", width=15)
        comb.grid(row=1, column=2, padx=(0, 5), sticky=tk.EW)
        return comb

    def __set_auto_update_checkbutton(self) -> Checkbutton:
        tip = Label(self.common_setting_frame, text="自动更新索引")
        tip.grid(row=2, column=1, padx=(5, 10), sticky=tk.E)
        checkbtn = Checkbutton(self.common_setting_frame, style="square-toggle")
        checkbtn.grid(row=2, column=2, padx=(0, 5), sticky=tk.EW)
        return checkbtn

    def __set_update_threads_count_scale(self) -> Scale:
        tip = Label(self.common_setting_frame, text="更新线程：$$")
        tip.grid(row=3, column=1, padx=(5, 10), sticky=tk.E)
        scale = Scale(self.common_setting_frame, from_=4, to=20, orient=tk.HORIZONTAL)
        scale.grid(row=3, column=2, padx=(0, 5), sticky=tk.EW)
        scale.config(command=lambda value: tip.config(text=f"更新线程:  {int(float(value)):0>2}"))
        return scale

    def __set_open_setting_btn(self) -> Button:
        button = Button(self.common_setting_frame, text="配置文件", takefocus=True, style=LINK, cursor="hand2")
        button.grid(row=4, column=1, pady=(5, 0), sticky=tk.E)
        return button

    def __set_open_open_repertory_btn(self) -> Button:
        button = Button(self.common_setting_frame, text="仓库地址", takefocus=True, style=LINK, cursor="hand2")
        button.grid(row=4, column=2, pady=(5, 0), padx=20, sticky=tk.W)
        return button


class WinGUI(TkinterDnD.Tk):
    search_tab: SearchFrame
    setting_tab: SettingFrame

    # 搜索控件
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

    # 设置控件
    index_dataset_table: Treeview
    index_tip_label: Label
    index_setting_frame: LabelFrame
    common_setting_frame: LabelFrame
    add_index_button: Button
    update_index_button: Button
    delete_index_button: Button
    rebuild_index_button: Button
    theme_combobox: Combobox
    auto_update_btn: Checkbutton
    update_threads_count_scale: Scale
    open_setting_file_button: Button
    open_repertory_button: Button

    def __init__(self) -> None:
        windll.shcore.SetProcessDpiAwareness(1)
        self._set_dpi_awareness()
        super().__init__()
        self.__win()
        self.switch_tab: Notebook = self.__set_notebook(self)
        self._expose_widgets()

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

    def _expose_widgets(self) -> None:
        """暴露搜索/设置页面的控件为顶层属性，供 CoreControl 直接访问。"""
        # 搜索控件
        self.search_entry = self.search_tab.search_entry
        self.filter_btn = self.search_tab.filter_btn
        self.search_by_browser_btn = self.search_tab.search_by_browser_btn
        self.search_by_clipboard_btn = self.search_tab.search_by_clipboard_btn
        self.more_options_button = self.search_tab.more_options_button
        self.filter_panel = self.search_tab.filter_panel
        self.preview_container = self.search_tab.preview_container
        self.preview_view = self.search_tab.preview_view
        self.preview_frame1 = self.search_tab.preview_frame1
        self.preview_frame2 = self.search_tab.preview_frame2
        self.preview_canvas1 = self.search_tab.preview_canvas1
        self.preview_canvas2 = self.search_tab.preview_canvas2
        # 设置控件
        self.index_dataset_table = self.setting_tab.index_dataset_table
        self.index_tip_label = self.setting_tab.index_tip_label
        self.index_setting_frame = self.setting_tab.index_setting_frame
        self.common_setting_frame = self.setting_tab.common_setting_frame
        self.add_index_button = self.setting_tab.add_index_button
        self.update_index_button = self.setting_tab.update_index_button
        self.delete_index_button = self.setting_tab.delete_index_button
        self.rebuild_index_button = self.setting_tab.rebuild_index_button
        self.theme_combobox = self.setting_tab.theme_combobox
        self.auto_update_btn = self.setting_tab.auto_update_btn
        self.update_threads_count_scale = self.setting_tab.update_threads_count_scale
        self.open_setting_file_button = self.setting_tab.open_setting_file_button
        self.open_repertory_button = self.setting_tab.open_repertory_button
