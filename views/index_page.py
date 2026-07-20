from __future__ import annotations

from tkinter.ttk import Frame, Label, Combobox, LabelFrame
import tkinter as tk

from ttkbootstrap.constants import LINK
from ttkbootstrap import Button, Checkbutton, Scale, tooltip

from config.settings import WinInfo, TkS
from utils.i18n import _
from views.widgets import DragReorderTreeview


class IndexFrame(Frame):
    index_tip_label: Label
    index_tooltip: tooltip.ToolTip
    index_dataset_table: DragReorderTreeview
    switch_model_combobox: Combobox
    add_index_button: Button
    update_index_button: Button
    delete_index_button: Button
    rebuild_index_button: Button
    auto_update_checkbutton: Checkbutton
    update_range_combobox: Combobox
    update_threads_count_scale: Scale
    exclude_button: Button
    clean_excluded_button: Button
    __slots__ = (
        "index_tip_label", "index_tooltip", "index_dataset_table", "switch_model_combobox",
        "add_index_button", "update_index_button", "delete_index_button",
        "rebuild_index_button", "auto_update_checkbutton", "update_range_combobox",
        "update_threads_count_scale", "exclude_button", "clean_excluded_button"
    )

    def __init__(self, parent, **kwargs) -> None:
        super().__init__(parent, **kwargs)
        self.place(relx=0, rely=0, relwidth=1, relheight=1)

        self.index_tip_label = self.__set_index_tip_label()
        self.index_tooltip = tooltip.ToolTip(self.index_tip_label, topmost=True)
        self.index_dataset_table = self.__set_index_dataset_table()
        index_setting_frame = self.__set_index_setting_frame()
        scan_setting_frame = self.__set_scan_setting_frame()
        self.switch_model_combobox = self.__set_switch_model_combobox(index_setting_frame)
        self.add_index_button = self.__set_index_btn(index_setting_frame, _("添加索引目录"), 1, pady_top=5)
        self.update_index_button = self.__set_index_btn(index_setting_frame, _("更新索引目录"), 2)
        self.delete_index_button = self.__set_index_btn(index_setting_frame, _("删除索引目录"), 3)
        self.rebuild_index_button = self.__set_index_btn(index_setting_frame, _("重建索引目录"), 4, pady_bottom=5)
        self.auto_update_checkbutton = self.__set_auto_update_checkbutton(scan_setting_frame)
        self.update_range_combobox = self.__set_update_range_combobox(scan_setting_frame)
        self.update_threads_count_scale = self.__set_update_threads_count_scale(scan_setting_frame)
        self.exclude_button = self.__set_exclude_button(scan_setting_frame)
        self.clean_excluded_button = self.__set_clean_excluded_button(scan_setting_frame)

    def __set_index_tip_label(self) -> Label:
        label = Label(self, text=_("当前索引的图库({count}张图片)", count="~"), anchor=tk.NW)
        label.place(relx=0.0081, rely=0.04, relwidth=1, relheight=0.0575)
        return label

    def __set_index_dataset_table(self) -> DragReorderTreeview:
        columns = [" ", _("图库目录")]
        table = DragReorderTreeview(self, show="headings", columns=columns)
        table.heading(0, text=columns[0], anchor=tk.CENTER)
        table.column(0, width=TkS(15), anchor=tk.CENTER, stretch=False)
        table.heading(1, text=columns[1], anchor=tk.CENTER)
        table.column(1, anchor=tk.CENTER)
        table.place(relx=0.0081, rely=0.1111, relwidth=0.7, relheight=0.888)
        return table

    def __set_index_setting_frame(self) -> LabelFrame:
        frame = LabelFrame(self, text=_("目录管理"))
        frame.place(relx=0.7181, rely=0.095, relwidth=0.2719, relheight=0.54)
        for i in range(5):
            frame.grid_rowconfigure(i, weight=1)
        frame.grid_columnconfigure(0, weight=2)
        frame.grid_columnconfigure(1, weight=1)
        return frame

    def __set_switch_model_combobox(self, parent) -> Combobox:
        container = Frame(parent)
        container.grid(row=0, column=0, columnspan=2, sticky=tk.EW, pady=TkS(2))
        Label(container, text=_("当前模型：")).pack(side=tk.LEFT, padx=TkS(5))
        combobox = Combobox(container, state="readonly", font=(WinInfo.default_font_family, WinInfo.default_font_size))
        combobox.pack(side=tk.LEFT, padx=(TkS(5), TkS(5)), expand=True, fill=tk.BOTH)
        return combobox

    def __set_index_btn(self, parent: LabelFrame, text: str, row: int, *, pady_top: int = 2, pady_bottom: int = 2) -> Button:
        btn = Button(parent, text=text, takefocus=False)
        btn.grid(
            row=row, column=0, padx=TkS(2), pady=(TkS(pady_top), TkS(pady_bottom)),
            ipadx=TkS(5), ipady=TkS(2), sticky=tk.NSEW, columnspan=2
        )
        return btn

    def __set_scan_setting_frame(self) -> LabelFrame:
        frame = LabelFrame(self, text=_("扫描设置"))
        frame.place(relx=0.7181, rely=0.64, relwidth=0.2719, relheight=0.36)
        for i in range(4):
            frame.grid_rowconfigure(i, weight=1)
        frame.grid_columnconfigure(0, weight=1, uniform='space')
        frame.grid_columnconfigure(1, weight=1, uniform='labels')
        frame.grid_columnconfigure(2, weight=1, uniform='controls')
        frame.grid_columnconfigure(3, weight=1, uniform='space')
        return frame

    def __set_auto_update_checkbutton(self, parent) -> Checkbutton:
        tip = Label(parent, text=_("索引自动更新"), anchor=tk.W)
        tip.grid(row=0, column=1, padx=(TkS(2), TkS(5)), sticky=tk.E)
        checkbtn = Checkbutton(parent, style="round-toggle")
        checkbtn.grid(row=0, column=2, padx=(0, TkS(2)), sticky=tk.EW)
        return checkbtn

    def __set_update_range_combobox(self, parent) -> Combobox:
        tip = Label(parent, text=_("索引更新范围"), anchor=tk.W)
        tip.grid(row=1, column=1, padx=(TkS(2), TkS(5)), sticky=tk.E)
        combobox = Combobox(
            parent, values=(_("当前模型"), _("全部模型")),
            width=10, state="readonly", font=(WinInfo.default_font_family, WinInfo.default_font_size)
        )
        combobox.grid(row=1, column=2, padx=(0, TkS(2)), sticky=tk.EW)
        return combobox

    def __set_update_threads_count_scale(self, parent) -> Scale:
        tip = Label(parent, text=_("更新线程：{count}", count=8), anchor=tk.W)
        tip.grid(row=2, column=1, padx=(TkS(2), TkS(5)), sticky=tk.E)
        scale = Scale(parent, from_=4, to=20, orient=tk.HORIZONTAL)
        scale.grid(row=2, column=2, padx=(0, TkS(2)), sticky=tk.EW)
        scale.config(command=lambda value: tip.config(text=_("更新线程:  {count:0>2}", count=int(float(value)))))
        return scale

    def __set_exclude_button(self, parent) -> Button:
        manage_btn = Button(parent, text=_("管理排除规则"), takefocus=False, cursor="hand2", style=LINK)
        manage_btn.grid(row=3, column=1, padx=(TkS(7), 0), sticky=tk.E)
        return manage_btn

    def __set_clean_excluded_button(self, parent) -> Button:
        btn = Button(parent, text=_("清理排除图片"), takefocus=False, cursor="hand2", style=LINK)
        btn.grid(row=3, column=2, padx=(TkS(2), 0), sticky=tk.W)
        return btn
