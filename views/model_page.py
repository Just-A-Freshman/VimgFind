from __future__ import annotations

from enum import StrEnum
import tkinter as tk

from ttkbootstrap import Button, Entry, Frame, Label, Labelframe, Progressbar, Treeview, Scrollbar, Text

from config.types import ModelConfig
from utils.i18n import _


class ModelStatus(StrEnum):
    DOWNLOADED = "downloaded"
    DOWNLOADING = "downloading"
    USING = "using"
    DISABLED = "disabled"


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
        self.detail_desc_text = Text(detail_frame, wrap='char', relief=tk.FLAT, bd=0, highlightthickness=0, autostyle=False)
        self.name_edit_entry = Entry(detail_frame)
        
        self.btn_group = Frame(control_frame)
        self.use_btn = Button(self.btn_group, text=_("使用模型"), takefocus=False, padding=(20, 10))
        self.uninstall_btn = Button(self.btn_group, text=_("卸载模型"), takefocus=False, padding=(20, 10), style="secondary")
        self.download_btn = Button(control_frame, text=_("下载模型"), takefocus=False, padding=(20, 10))
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
        entry.grid(row=0, column=0, pady=(5, 5), padx=5, ipady=5, sticky=tk.EW)
        return entry

    def __set_browser_button(self, parent) -> Button:
        browser_button = Button(parent, text=_("加载本地模型"), takefocus=False)
        browser_button.grid(row=0, column=1, pady=(5, 5), padx=5, ipady=5, sticky=tk.EW)
        return browser_button

    def __set_model_tree(self, parent) -> Treeview:
        columns_info = [(_("名称"), 40), (_("标签"), 30), (_("类型"), 30), (_("大小"), 30)]
        tree = Treeview(parent, show="headings", columns=[i[0] for i in columns_info])
        tree.grid(row=1, column=0, columnspan=2, sticky=tk.NSEW, padx=5)
        for text, width in columns_info:
            tree.heading(text, text=text, anchor=tk.CENTER)
            tree.column(text, anchor=tk.CENTER, width=width, stretch=True)
        scrollbar = Scrollbar(tree, orient=tk.VERTICAL, cursor="hand2")
        scrollbar.pack(fill=tk.BOTH, side=tk.RIGHT, pady=(1, 1), padx=1)
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
        frame.grid(row=2, column=0, columnspan=2, sticky=tk.EW, pady=(8, 5))
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
        self.name_tip_label.config(text=_("名称："))
        self.name_tip_label.grid(row=0, column=0, sticky=tk.W, padx=(5, 2), pady=5)
        self.name_edit_entry.config(state=tk.NORMAL, cursor="xterm")
        self.name_edit_entry.delete(0, tk.END)
        self.name_edit_entry.insert(0, name)
        self.name_edit_entry.grid(row=0, column=1, sticky=tk.EW, padx=(0, 5), pady=5, ipady=5)
        self.detail_desc_text.config(state=tk.NORMAL)
        self.detail_desc_text.delete('1.0', tk.END)
        text = _("描述：{desc}\n\n下载地址：{url}", desc=model_config.meta.description, url=model_config.meta.download_url)
        self.detail_desc_text.insert(tk.END, text)
        self.detail_desc_text.grid(row=1, column=0, columnspan=2, sticky=tk.NSEW, padx=5, pady=(0, 5))
        self.detail_desc_text.config(state=tk.DISABLED)

        if status == ModelStatus.DISABLED:
            self.name_edit_entry.config(state=tk.DISABLED, cursor="arrow")
            self.download_btn.grid(row=0, column=0, columnspan=3, pady=(3, 20))
        elif status == ModelStatus.DOWNLOADING:
            self.name_edit_entry.config(state=tk.DISABLED, cursor="arrow")
        else:
            self.btn_group.grid(row=0, column=0, columnspan=3, pady=(3, 20))
            self.use_btn.grid(row=0, column=0, sticky=tk.EW, padx=(0, 5))
            self.uninstall_btn.grid(row=0, column=1, sticky=tk.EW)
            self.use_btn.config(state=tk.DISABLED if status == "using" else tk.NORMAL)
            self.uninstall_btn.config(state=tk.DISABLED if status == "using" else tk.NORMAL)

    def show_default(self) -> None:
        self.__hide_widgets()
        self.name_tip_label.config(text=_("选择模型查看详细信息"))
        self.name_tip_label.grid(row=1, column=0, columnspan=2)
