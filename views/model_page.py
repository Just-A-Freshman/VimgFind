from __future__ import annotations

import tkinter as tk

from ttkbootstrap import Button, Entry, Frame, Label, Labelframe, Progressbar, Style, Treeview, Scrollbar, Text

from config.settings import WinInfo, TkS, ACTIVE_MARKER
from config.types import ModelConfig
from utils.i18n import _


class ModelFrame(Frame):
    load_local_model_entry: Entry
    model_tree: Treeview
    detail_frame: Labelframe
    detail_desc_text: Text
    use_btn: Button
    uninstall_btn: Button
    download_btn: Button
    download_progressbar: Progressbar
    download_progress_label: Label
    download_control_btn: Button
    download_cancel_btn: Button
    __slots__ = (
        "load_local_model_entry", "model_tree",
        "btn_group", "detail_desc_text", "use_btn",
        "uninstall_btn", "download_btn",
        "download_progressbar", "download_progress_label",
        "download_control_btn", "download_cancel_btn",
        "name_tip_label", "browser_button", "name_edit_entry", 
    )

    def __init__(self, parent, **kwargs) -> None:
        super().__init__(parent, **kwargs)

        model_list_frame = self.__set_model_list_frame()
        detail_frame = self.__set_detail_frame()
        control_frame = self.__set_control_frame(detail_frame)

        self.load_local_model_entry = self.__set_load_local_model_entry(model_list_frame)
        self.browser_button = self.__set_browser_button(model_list_frame)
        self.model_tree = self.__set_model_tree(model_list_frame)
        self.name_tip_label = Label(detail_frame)
        self.detail_desc_text = Text(detail_frame, wrap='char', relief=tk.FLAT, autostyle=False)
        self.name_edit_entry = Entry(detail_frame)
        
        self.btn_group = Frame(control_frame)
        self.use_btn = Button(self.btn_group, text=_("使用模型"), takefocus=False, padding=(TkS(20), TkS(10)))
        self.uninstall_btn = Button(self.btn_group, text=_("卸载模型"), takefocus=False, padding=(TkS(20), TkS(10)), style="secondary")
        self.download_btn = Button(control_frame, text=_("下载模型"), takefocus=False, padding=(TkS(20), TkS(10)))
        self.download_progressbar = Progressbar(control_frame, orient=tk.HORIZONTAL, mode="determinate", maximum=100)
        self.download_progress_label = Label(control_frame, text="")
        self.download_control_btn = Button(control_frame, style="link", takefocus=False, text=_("暂停"))
        self.download_cancel_btn = Button(control_frame, style="link", takefocus=False, text=_("取消"))
        self.btn_group.grid_columnconfigure(0, weight=1, uniform="btn_group")
        self.btn_group.grid_columnconfigure(1, weight=1, uniform="btn_group")
        self.show_default()

    def __set_model_list_frame(self) -> Labelframe:
        frame = Labelframe(self, text=_("模型列表"))
        frame.place(relx=0.01, rely=0.02, relwidth=0.57, relheight=0.98)
        frame.grid_rowconfigure(0, weight=0)
        frame.grid_rowconfigure(1, weight=1)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=0)
        return frame

    def __set_load_local_model_entry(self, parent) -> Entry:
        entry = Entry(parent)
        entry.grid(row=0, column=0, pady=(TkS(5), TkS(5)), padx=TkS(5), ipady=TkS(5), sticky=tk.EW)
        return entry

    def __set_browser_button(self, parent) -> Button:
        browser_button = Button(parent, text=_("加载本地模型"), takefocus=False)
        browser_button.grid(row=0, column=1, pady=(TkS(5), TkS(5)), padx=TkS(5), ipady=TkS(5), sticky=tk.EW)
        return browser_button

    def __set_model_tree(self, parent) -> Treeview:
        columns = [_("名称"), _("标签"), _("类型"), _("大小")]
        tree = Treeview(parent, show="headings", columns=columns)
        tree.grid(row=1, column=0, columnspan=2, sticky=tk.NSEW, padx=TkS(5))
        col_widths = {_("名称"): TkS(40), _("标签"): TkS(30), _("类型"): TkS(30), _("大小"): TkS(30)}
        for col in columns:
            tree.heading(col, text=col, anchor=tk.CENTER)
            tree.column(col, anchor=tk.CENTER, width=col_widths[col], stretch=True)
        scrollbar = Scrollbar(tree, orient=tk.VERTICAL, cursor="hand2")
        scrollbar.pack(fill=tk.BOTH, side=tk.RIGHT, pady=(TkS(1), TkS(1)), padx=TkS(1))
        scrollbar.config(command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        return tree

    def __set_detail_frame(self) -> Labelframe:
        frame = Labelframe(self, text=_("模型详情"))
        frame.place(relx=0.59, rely=0.02, relwidth=0.40, relheight=0.98)
        frame.grid_rowconfigure(0, weight=0)
        frame.grid_rowconfigure(1, weight=1)
        frame.grid_rowconfigure(2, weight=0)
        frame.grid_columnconfigure(0, weight=0)
        frame.grid_columnconfigure(1, weight=1)
        return frame

    def __set_control_frame(self, parent) -> Frame:
        frame = Frame(parent)
        frame.grid(row=2, column=0, columnspan=2, sticky=tk.EW, pady=(TkS(8), TkS(5)))
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=0)
        frame.grid_columnconfigure(2, weight=0)
        return frame

    def __hide_widgets(self) -> None:
        self.btn_group.grid_forget()
        for w in (
            self.name_tip_label, self.name_edit_entry, self.detail_desc_text,
            self.download_btn, self.download_progressbar, self.download_progress_label, 
            self.download_control_btn, self.download_cancel_btn
        ):
            w.grid_forget()

    def show_detail(self, model_config: ModelConfig) -> None:
        self.__hide_widgets()
        selection = self.model_tree.selection()
        name = self.model_tree.item(selection[0], "values")[0] if selection else ""
        status = self.model_tree.item(selection[0], "tags")[0] if selection else ""
        name = name.removeprefix(ACTIVE_MARKER)

        self.name_tip_label.config(text=_("名称："))
        self.name_tip_label.grid(row=0, column=0, sticky=tk.W, padx=(TkS(5), TkS(2)), pady=TkS(5))
        self.name_edit_entry.config(state=tk.NORMAL, cursor="xterm")
        self.name_edit_entry.delete(0, tk.END)
        self.name_edit_entry.insert(0, name)
        self.name_edit_entry.grid(row=0, column=1, sticky=tk.EW, padx=(0, TkS(5)), pady=TkS(5), ipady=TkS(5))
        self.detail_desc_text.config(state=tk.NORMAL)
        self.detail_desc_text.delete('1.0', tk.END)
        text = _("描述：{desc}\n\n下载地址：{url}", desc=model_config.meta.description, url=model_config.meta.download_url)
        self.detail_desc_text.insert(tk.END, text)
        self.detail_desc_text.grid(row=1, column=0, columnspan=2, sticky=tk.NSEW, padx=TkS(5), pady=(0, TkS(5)))
        self.detail_desc_text.config(state=tk.DISABLED)

        if status == "not download":
            self.name_edit_entry.config(state=tk.DISABLED, cursor="arrow")
            self.download_btn.grid(row=0, column=0, columnspan=3, pady=(TkS(3), TkS(20)))
        elif status == "downloading":
            self.name_edit_entry.config(state=tk.DISABLED, cursor="arrow")
        else:
            self.btn_group.grid(row=0, column=0, columnspan=3, pady=(TkS(3), TkS(20)))
            self.use_btn.grid(row=0, column=0, sticky=tk.EW, padx=(0, TkS(5)))
            self.uninstall_btn.grid(row=0, column=1, sticky=tk.EW)
            self.use_btn.config(state=tk.DISABLED if status == "using" else tk.NORMAL)
            self.uninstall_btn.config(state=tk.DISABLED if status == "using" else tk.NORMAL)

    def show_default(self) -> None:
        self.__hide_widgets()
        self.name_tip_label.config(text=_("选择模型查看详细信息"))
        self.name_tip_label.grid(row=1, column=0, columnspan=2)
