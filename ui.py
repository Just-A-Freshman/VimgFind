from ttkbootstrap import Button, Entry, Checkbutton, Scale, Style
from ttkbootstrap.constants import LINK
from tkinter.ttk import (
    Notebook, Frame, Treeview, Label, LabelFrame, Combobox, Scrollbar
)
from tkinterdnd2 import TkinterDnD
import tkinter as tk
from tkinter import filedialog
from threading import Thread
from ctypes import windll
from pathlib import Path


from setting import WinInfo
from widgets import BasicImagePreviewView, PreviewCanvasView
from utils import FileOperation



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
            row=0, column=0, sticky='w', padx=(12, 0), pady=(20, 10)
        )
        self.sim_scale = Scale(self, from_=0, to=100, orient=tk.HORIZONTAL)
        self.sim_scale.grid(row=0, column=1, columnspan=4, sticky='ew', padx=(8, 4), pady=(20, 10))
        self.sim_value = Label(self, text="0%", width=5)
        self.sim_value.grid(row=0, column=5, sticky='e', pady=(20, 10))

        # 第 1 行：文件类型
        Label(self, text="文件类型", width=10, anchor=tk.W).grid(
            row=1, column=0, sticky='w', padx=(12, 0), pady=(10, 10)
        )
        self.ext_combo = Combobox(
            self,
            values=["所有图片文件", "PNG", "JPG/JPEG", "WebP", "GIF", "BMP", "TIFF"],
            state="readonly",
        )
        self.ext_combo.grid(row=1, column=1, columnspan=5, sticky='ew', padx=(8, 0), pady=(10, 10))
        self.ext_combo.current(0)

        # 第 2 行：文件大小
        Label(self, text="文件大小", width=10, anchor=tk.W).grid(
            row=2, column=0, sticky='w', padx=(12, 0), pady=(10, 10)
        )
        self.size_min = Entry(self, width=6)
        self.size_min.grid(row=2, column=1, sticky='ew', padx=(8, 2), pady=(10, 10))
        self.size_min_unit = Combobox(self, values=["KB", "MB"], state="readonly", width=4)
        self.size_min_unit.grid(row=2, column=2, sticky='ew', padx=(0, 4), pady=(10, 10))
        self.size_min_unit.current(1)
        Label(self, text="到").grid(row=2, column=3, pady=(10, 10))
        self.size_max = Entry(self, width=6)
        self.size_max.grid(row=2, column=4, sticky='ew', padx=(4, 2), pady=(10, 10))
        self.size_max_unit = Combobox(self, values=["KB", "MB"], state="readonly", width=4)
        self.size_max_unit.grid(row=2, column=5, sticky='ew', padx=(0, 0), pady=(10, 10))
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
            padx=(8, 0), pady=(10, 2)
        )
        lbox_frame.grid_columnconfigure(0, weight=1)
        self.folder_listbox = tk.Listbox(
            lbox_frame, selectmode=tk.MULTIPLE,
            height=5, width=1, activestyle='none',
            exportselection=False, justify=tk.LEFT
        )
        self.folder_listbox.grid(row=0, column=0, sticky='ew')

        # 底部按钮
        btn_frame = Frame(self)
        btn_frame.grid(row=4, column=0, columnspan=7, pady=(14, 30))
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
        btn.place(
            in_=self.search_entry, relx=1.0, rely=0.1, anchor='ne',
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
    exclude_button: Button
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
        self.exclude_button = self.__set_exclude_button()
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
        frame.grid_columnconfigure(0, weight=7, uniform='btn')
        frame.grid_columnconfigure(1, weight=3, uniform='btn')
        return frame

    def __set_add_index_button(self) -> Button:
        btn = Button(self.index_setting_frame, text="添加索引目录", takefocus=False)
        btn.grid(row=0, column=0, padx=(5, 2), pady=(10, 5), ipadx=6, ipady=5, sticky=tk.NSEW)
        return btn

    def __set_exclude_button(self) -> Button:
        btn = Button(self.index_setting_frame, text="排除", style="secondary", takefocus=False)
        btn.grid(row=0, column=1, padx=(2, 5), pady=(10, 5), ipadx=6, ipady=5, sticky=tk.NSEW)
        return btn

    def __set_update_index_button(self) -> Button:
        btn = Button(self.index_setting_frame, text="更新索引目录", takefocus=False)
        btn.grid(row=1, column=0, columnspan=2, padx=5, pady=5, ipadx=10, ipady=5, sticky=tk.NSEW)
        return btn

    def __set_delete_index_button(self) -> Button:
        btn = Button(self.index_setting_frame, text="删除索引目录", takefocus=False)
        btn.grid(row=2, column=0, columnspan=2, padx=5, pady=5, ipadx=10, ipady=5, sticky=tk.NSEW)
        return btn

    def __set_rebuild_index_button(self) -> Button:
        btn = Button(self.index_setting_frame, text="重建索引目录", takefocus=False)
        btn.grid(row=3, column=0, columnspan=2, padx=5, pady=(5, 10), ipadx=10, ipady=5, sticky=tk.NSEW)
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
        button = Button(self.common_setting_frame, text="检查更新", takefocus=True, style=LINK, cursor="hand2")
        button.grid(row=4, column=2, pady=(5, 0), padx=50, sticky=tk.W)
        return button


class WinGUI(TkinterDnD.Tk):
    search_tab: SearchFrame
    setting_tab: SettingFrame

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

    index_dataset_table: Treeview
    index_tip_label: Label
    index_setting_frame: LabelFrame
    common_setting_frame: LabelFrame
    add_index_button: Button
    exclude_button: Button
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

        self.index_dataset_table = self.setting_tab.index_dataset_table
        self.index_tip_label = self.setting_tab.index_tip_label
        self.index_setting_frame = self.setting_tab.index_setting_frame
        self.common_setting_frame = self.setting_tab.common_setting_frame
        self.add_index_button = self.setting_tab.add_index_button
        self.exclude_button = self.setting_tab.exclude_button
        self.update_index_button = self.setting_tab.update_index_button
        self.delete_index_button = self.setting_tab.delete_index_button
        self.rebuild_index_button = self.setting_tab.rebuild_index_button
        self.theme_combobox = self.setting_tab.theme_combobox
        self.auto_update_btn = self.setting_tab.auto_update_btn
        self.update_threads_count_scale = self.setting_tab.update_threads_count_scale
        self.open_setting_file_button = self.setting_tab.open_setting_file_button
        self.open_repertory_button = self.setting_tab.open_repertory_button


class ExcludeDialog(tk.Toplevel):
    def __init__(self, parent, setting) -> None:
        super().__init__(parent)
        self.withdraw()  # 隐藏初始窗口，避免 geometry 设置前闪现
        self.setting = setting
        self.result: bool | None = None  # True=保存, None=取消

        self._cancel_scan = False
        self._scan_thread: Thread | None = None

        self.title("排除设置")
        self.iconbitmap(WinInfo.ico_path)
        win_w = WinInfo.TkS(620)
        win_h = WinInfo.TkS(520)
        # 按钮 padding 基于对话框参考高度等比缩放
        self._ipady = max(4, win_h // 81)
        self._ipadx = max(4, win_h // 56)
        x = parent.winfo_rootx() + (parent.winfo_width() - win_w) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - win_h) // 2
        self.geometry(f"{win_w}x{win_h}+{x}+{y}")
        self.minsize(500, 400)
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_save)

        self._build_upper()
        self._build_lower()

        self._load_rules()
        self.deiconify()  # 所有组件就绪后再显示

    # ── 上半块：排除规则 ──────────────────────────────────────────

    def _build_upper(self) -> None:
        frame = LabelFrame(self, text="排除规则")
        frame.place(relx=0.04, rely=0.03, relwidth=0.92, relheight=0.40)

        btn_frame = tk.Frame(frame)
        btn_frame.pack(fill=tk.X, padx=4, pady=(6, 10))
        Button(btn_frame, text="新建规则", command=self._on_add_name,
               takefocus=False, cursor="hand2").pack(side=tk.LEFT, padx=(0, 10), ipadx=self._ipadx, ipady=self._ipady)
        Button(btn_frame, text="删除规则", command=self._on_delete_selected,
               takefocus=False, cursor="hand2").pack(side=tk.LEFT, ipadx=self._ipadx, ipady=self._ipady)

        tree_frame = tk.Frame(frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=(4, 4))
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        # 使用全局 Treeview 行高（control.py 中设为 50）

        self.rules_tree = Treeview(
            tree_frame, columns=("name",), show="",
            selectmode="browse", cursor="hand2"
        )
        self.rules_tree.column("name", stretch=True)
        self.rules_tree.grid(row=0, column=0, sticky=tk.NSEW)
        self.rules_tree.bind("<Double-Button-1>", self._on_item_double_click)

        scroll = Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.rules_tree.yview)
        scroll.grid(row=0, column=1, sticky=tk.NS)
        self.rules_tree.configure(yscrollcommand=scroll.set)

    # ── 下半块：预览排除效果 ──────────────────────────────────────

    def _build_lower(self) -> None:
        frame = LabelFrame(self, text="选择任意文件夹预览排除效果")
        frame.place(relx=0.04, rely=0.46, relwidth=0.92, relheight=0.53)

        # 路径栏 + 浏览按钮
        path_frame = tk.Frame(frame)
        path_frame.pack(fill=tk.X, padx=4, pady=(0, 10))
        self.preview_path_var = tk.StringVar()
        self.preview_path_entry = Entry(path_frame, textvariable=self.preview_path_var)
        self.preview_path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4), ipady=self._ipady)
        self.browse_btn = Button(path_frame, text="浏览", command=self._on_browse_preview,
                                 takefocus=False, cursor="hand2")
        self.browse_btn.pack(side=tk.RIGHT, ipadx=self._ipadx * 2, ipady=self._ipady)

        # 底部状态提示（输入框与列表之间）
        self.preview_status_var = tk.StringVar()
        self.preview_status_label = Label(frame, textvariable=self.preview_status_var, anchor=tk.W)
        self.preview_status_label.pack(fill=tk.X, padx=4, pady=(0, 2))

        # 预览结果 Treeview
        tree_frame = tk.Frame(frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=0)
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        self.preview_tree = Treeview(
            tree_frame, columns=("path",), show="",
            cursor="hand2"
        )
        self.preview_tree.column("path", stretch=True)
        self.preview_tree.grid(row=0, column=0, sticky=tk.NSEW)
        self.preview_tree.bind("<Double-Button-1>", self._on_preview_double_click)

        preview_scroll_v = Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.preview_tree.yview)
        preview_scroll_v.grid(row=0, column=1, sticky=tk.NS)
        preview_scroll_h = Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.preview_tree.xview)
        preview_scroll_h.grid(row=1, column=0, columnspan=2, sticky=tk.EW)
        self.preview_tree.configure(
            yscrollcommand=preview_scroll_v.set,
            xscrollcommand=preview_scroll_h.set
        )

    # ── 规则操作 ──────────────────────────────────────────────────

    def _load_rules(self) -> None:
        rules: list[str] = self.setting.get_config("index", "exclude_rules") or []
        for rule in rules:
            self.rules_tree.insert("", tk.END, values=(rule,))
        self.preview_status_var.set("被排除索引的文件夹")

    def _collect_rules(self) -> list[str]:
        rules: list[str] = []
        for child in self.rules_tree.get_children():
            text = self.rules_tree.item(child, "values")[0].strip()
            if text:
                rules.append(text)
        return rules

    def _edit_item(self, iid: str, initial_text: str = "") -> None:
        """在指定 item 行上创建 Entry 进行编辑（新建/双击修改共用）"""
        if hasattr(self, '_rule_entry') and self._rule_entry and self._rule_entry.winfo_exists():
            self._rule_entry.destroy()

        tree = self.rules_tree
        # 编辑期间暂时取消高亮
        tree.selection_remove(*tree.selection())
        parent = tree.master

        tree.update_idletasks()
        item_bbox = tree.bbox(iid, column="name")
        if item_bbox:
            ix, iy, _, ih = item_bbox
            entry_x = tree.winfo_x() + ix
            entry_y = tree.winfo_y() + iy
            entry_h = ih
        else:
            row_height = 50
            children = tree.get_children()
            row_idx = children.index(iid)
            entry_x = 2
            entry_y = row_idx * row_height + 2
            entry_h = row_height

        entry_w = tree.winfo_width()
        tv_font = Style().lookup("Treeview", "font") or "TkDefaultFont"

        entry = tk.Entry(parent, font=tv_font, bd=0, highlightthickness=1)
        entry.insert(0, initial_text)
        entry.select_range(0, tk.END)
        entry.icursor(tk.END)
        self._rule_entry = entry

        _confirming = False
        def on_confirm(event=None):
            nonlocal _confirming
            if _confirming:
                return
            _confirming = True
            text = entry.get().strip()
            if text:
                tree.item(iid, values=(text,))
                tree.selection_set(iid)
                tree.focus(iid)
                self._trigger_preview()
            elif not initial_text:
                # 新建模式下空内容则删除该行
                tree.delete(iid)
            entry.master.after_idle(entry.destroy)

        def on_cancel(event=None):
            """Escape 取消编辑，新建模式删空行，编辑模式恢复原值"""
            nonlocal _confirming
            if _confirming:
                return
            _confirming = True
            if not initial_text:
                tree.delete(iid)
            entry.master.after_idle(entry.destroy)

        entry.place(x=entry_x, y=entry_y, width=entry_w, height=entry_h)
        entry.focus_set()
        entry.bind("<Return>", on_confirm)
        entry.bind("<FocusOut>", on_confirm)
        entry.bind("<Escape>", on_cancel)

    def _on_add_name(self) -> None:
        """在 Treeview 底部插入空行，进入编辑"""
        iid = self.rules_tree.insert("", tk.END, values=("",))
        self.rules_tree.yview_moveto(1.0)
        self._edit_item(iid, "")

    def _on_item_double_click(self, event: tk.Event) -> None:
        """双击已有规则进行编辑"""
        iid = self.rules_tree.identify_row(event.y)
        if not iid:
            return
        text = self.rules_tree.item(iid, "values")[0]
        self._edit_item(iid, text)

    def _on_delete_selected(self) -> None:
        selected = self.rules_tree.selection()
        if selected:
            self.rules_tree.delete(*selected)
            self._trigger_preview()

    # ── 预览扫描 ──────────────────────────────────────────────────

    def _trigger_preview(self) -> None:
        # 取消前一次扫描
        self._cancel_scan = True

        dir_path = self.preview_path_var.get().strip()
        if not dir_path or not Path(dir_path).is_dir():
            return

        # 清空旧结果
        self.preview_tree.delete(*self.preview_tree.get_children())
        self.preview_status_var.set("正在扫描目录结构...（关闭窗口终止扫描）")

        rules = self._collect_rules()
        if not rules:
            self.preview_status_var.set("被排除索引的文件夹")
            return

        self._cancel_scan = False
        self._scan_thread = Thread(
            target=self._do_preview, args=(dir_path, rules), daemon=True
        )
        self._scan_thread.start()

    def _do_preview(self, target_dir: str, rules: list[str]) -> None:
        try:
            matched = FileOperation.preview_exclusion(target_dir, rules)
        except Exception:
            matched = []

        if not self._cancel_scan:
            self.after(0, lambda: self._update_preview(matched))

    def _update_preview(self, matched: list[str]) -> None:
        self.preview_status_var.set("被排除索引的文件夹")
        for path in matched:
            self.preview_tree.insert("", tk.END, values=(path,))

    def _on_browse_preview(self) -> None:
        dir_path = filedialog.askdirectory(title="选择要预览的目录")
        if dir_path:
            self.preview_path_var.set(dir_path)
            self._trigger_preview()

    def _on_preview_double_click(self, event: tk.Event) -> None:
        item = self.preview_tree.identify_row(event.y)
        if not item:
            return
        path = self.preview_tree.item(item, "values")[0].strip()
        if path and Path(path).is_dir():
            FileOperation.open_file(path)

    # ── 保存 / 取消 ──────────────────────────────────────────────

    def _on_save(self) -> None:
        self._cancel_scan = True
        rules = self._collect_rules()
        self.setting.modity_config("index", "exclude_rules", rules)
        self.setting.save_settings()
        self.result = True
        self.destroy()
