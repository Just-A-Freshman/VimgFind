from ttkbootstrap import Button, Checkbutton, Scale, Style
from ttkbootstrap.constants import LINK
from tkinter.ttk import Frame, Treeview, Label, LabelFrame, Combobox
import tkinter as tk


class SettingFrame(Frame):
    index_tip_label: Label
    index_dataset_table: Treeview
    index_setting_frame: LabelFrame
    scan_setting_frame: LabelFrame
    common_setting_frame: LabelFrame
    add_index_button: Button
    exclude_button: Button
    clean_excluded_button: Button
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
        self.scan_setting_frame = self.__set_scan_setting_frame()
        self.common_setting_frame = self.__set_common_setting_frame()
        self.add_index_button = self.__set_add_index_button()
        self.update_index_button = self.__set_update_index_button()
        self.delete_index_button = self.__set_delete_index_button()
        self.rebuild_index_button = self.__set_rebuild_index_button()
        self.theme_combobox = self.__set_theme_combobox()
        self.auto_update_btn = self.__set_auto_update_checkbutton()
        self.update_threads_count_scale = self.__set_update_threads_count_scale()
        self.exclude_button = self.__set_exclude_button()
        self.clean_excluded_button = self.__set_clean_excluded_button()
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
        frame = LabelFrame(self, text="目录管理")
        frame.place(relx=0.7181, rely=0.095, relwidth=0.2719, relheight=0.44)
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

    def __set_scan_setting_frame(self) -> LabelFrame:
        frame = LabelFrame(self, text="扫描设置")
        frame.place(relx=0.7181, rely=0.54, relwidth=0.2719, relheight=0.26)
        for i in range(3):
            frame.grid_rowconfigure(i, weight=1)
        frame.grid_columnconfigure(0, weight=1, uniform='space')
        frame.grid_columnconfigure(1, weight=1, uniform='labels')
        frame.grid_columnconfigure(2, weight=1, uniform='controls')
        frame.grid_columnconfigure(3, weight=1, uniform='space')
        return frame

    def __set_auto_update_checkbutton(self) -> Checkbutton:
        tip = Label(self.scan_setting_frame, text="自动更新索引", anchor=tk.W)
        tip.grid(row=0, column=1, padx=(5, 10), sticky=tk.E)
        checkbtn = Checkbutton(self.scan_setting_frame, style="round-toggle")
        checkbtn.grid(row=0, column=2, padx=(0, 5), sticky=tk.EW)
        return checkbtn

    def __set_update_threads_count_scale(self) -> Scale:
        tip = Label(self.scan_setting_frame, text="更新线程：8", anchor=tk.W)
        tip.grid(row=1, column=1, padx=(5, 10), sticky=tk.E)
        scale = Scale(self.scan_setting_frame, from_=4, to=20, orient=tk.HORIZONTAL)
        scale.grid(row=1, column=2, padx=(0, 5), sticky=tk.EW)
        scale.config(command=lambda value: tip.config(text=f"更新线程:  {int(float(value)):0>2}"))
        return scale

    def __set_exclude_button(self) -> Button:
        manage_btn = Button(
            self.scan_setting_frame, text="管理排除规则",
            takefocus=False, cursor="hand2", style=LINK
        )
        manage_btn.grid(row=2, column=1, padx=(15, 0), sticky=tk.E)
        return manage_btn

    def __set_clean_excluded_button(self) -> Button:
        btn = Button(
            self.scan_setting_frame, text="清理排除图片",
            takefocus=False, cursor="hand2", style=LINK
        )
        btn.grid(row=2, column=2, padx=(5, 0), sticky=tk.W)
        return btn

    def __set_common_setting_frame(self) -> LabelFrame:
        frame = LabelFrame(self, text="通用设置")
        frame.place(relx=0.7181, rely=0.805, relwidth=0.2719, relheight=0.175)
        for i in range(2):
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
        tip.grid(row=0, column=1, padx=(5, 10), sticky=tk.E)
        comb = Combobox(self.common_setting_frame, values=theme_names, state="readonly", width=15)
        comb.grid(row=0, column=2, padx=(0, 5), sticky=tk.EW)
        return comb

    def __set_open_setting_btn(self) -> Button:
        button = Button(self.common_setting_frame, text="配置文件", takefocus=True, style=LINK, cursor="hand2")
        button.grid(row=1, column=1, pady=(5, 0), sticky=tk.E)
        return button

    def __set_open_open_repertory_btn(self) -> Button:
        button = Button(self.common_setting_frame, text="检查更新", takefocus=True, style=LINK, cursor="hand2")
        button.grid(row=1, column=2, pady=(5, 0), padx=50, sticky=tk.W)
        return button
