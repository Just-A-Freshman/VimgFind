from ttkbootstrap import Button, Entry, Frame, Label, Labelframe, Progressbar, Treeview, Scrollbar, Text
import tkinter as tk

from config.types import ModelConfig
from config.settings import WinInfo, TkS, STATUS_LABEL


class ModelFrame(Frame):
    load_local_model_entry: Entry
    model_tree: Treeview
    detail_frame: Labelframe
    local_model_frame: Labelframe
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
        "detail_frame", "local_model_frame",
        "detail_desc_text", "use_btn",
        "uninstall_btn", "download_btn",
        "download_progressbar", "download_progress_label",
        "download_control_btn", "download_cancel_btn",
        "name_tip_label", "broswer_button", "name_edit_entry",
    )

    def __init__(self, parent, **kwargs) -> None:
        super().__init__(parent, **kwargs)

        model_list_frame = self.__set_model_list_frame()
        detail_frame = self.__set_detail_frame()

        self.load_local_model_entry = self.__set_load_local_model_entry(model_list_frame)
        self.broswer_button = self.__set_broswer_button(model_list_frame)
        self.model_tree = self.__set_model_tree(model_list_frame)
        self.name_tip_label = Label(detail_frame)
        self.detail_desc_text = Text(
            detail_frame, wrap='char', relief=tk.FLAT, autostyle=False,    # type:ignore
            font=(WinInfo.default_font_family, WinInfo.default_font_size)
        )
        self.name_edit_entry = Entry(detail_frame, font=(WinInfo.default_font_family, WinInfo.default_font_size))
        self.use_btn = Button(detail_frame, text="使用模型", takefocus=False, padding=(TkS(15), TkS(5)))
        self.uninstall_btn = Button(detail_frame, text="卸载模型", takefocus=False, padding=(TkS(15), TkS(5)), style="secondary")
        self.download_btn = Button(detail_frame, text="下载模型", takefocus=False, padding=(TkS(15), TkS(5)))
        self.download_progressbar = Progressbar(detail_frame, orient=tk.HORIZONTAL, mode="determinate", maximum=100)
        self.download_progress_label = Label(detail_frame, text="")
        self.download_control_btn = Button(detail_frame, style="link", takefocus=False, text="暂停")
        self.download_cancel_btn = Button(detail_frame, style="link", takefocus=False, text="取消")
        self.show_default()

    def __set_model_list_frame(self) -> Labelframe:
        frame = Labelframe(self, text="模型列表")
        frame.place(relx=0.01, rely=0.02, relwidth=0.57, relheight=0.98)
        frame.grid_rowconfigure(0, weight=0)
        frame.grid_rowconfigure(1, weight=1)
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_columnconfigure(1, weight=0)
        return frame

    def __set_load_local_model_entry(self, parent) -> Entry:
        entry = Entry(parent, font=(WinInfo.default_font_family, WinInfo.default_font_size))
        entry.grid(row=0, column=0, pady=(TkS(5), TkS(5)), padx=TkS(5), ipady=TkS(5), sticky=tk.EW)
        return entry

    def __set_broswer_button(self, parent) -> Button:
        broswer_button = Button(parent, text="加载本地模型", takefocus=False)
        broswer_button.grid(row=0, column=1, pady=(TkS(5), TkS(5)), padx=TkS(5), ipady=TkS(5), sticky=tk.EW)
        return broswer_button

    def __set_model_tree(self, parent) -> Treeview:
        columns = ["名称", "标签", "类型", "大小", "状态"]
        tree = Treeview(parent, show="headings", columns=columns)
        tree.grid(row=1, column=0, columnspan=2, sticky=tk.NSEW, padx=TkS(5))
        col_widths = {"名称": TkS(40), "标签": TkS(30), "类型": TkS(30), "大小": TkS(30), "状态": TkS(30)}
        for col in columns:
            tree.heading(col, text=col, anchor=tk.CENTER)
            tree.column(col, anchor=tk.CENTER, width=col_widths[col], stretch=True)
        scrollbar = Scrollbar(tree, orient=tk.VERTICAL, cursor="hand2")
        scrollbar.pack(fill=tk.BOTH, side=tk.RIGHT, pady=(TkS(1), TkS(1)), padx=TkS(1))
        scrollbar.config(command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        return tree

    def __set_detail_frame(self) -> Labelframe:
        frame = Labelframe(self, text="模型详情")
        frame.place(relx=0.59, rely=0.02, relwidth=0.40, relheight=0.98)
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)
        return frame

    def show_detail(self, model_config: ModelConfig) -> None:
        for w in (
            self.detail_desc_text, self.use_btn, self.uninstall_btn,
            self.download_btn, self.download_progress_label, self.download_progressbar,
            self.download_control_btn, self.download_cancel_btn,
        ):
            w.place_forget()

        selection = self.model_tree.selection()
        name = self.model_tree.item(selection[0], "values")[0] if selection else ""
        status = self.model_tree.item(selection[0], "values")[-1] if selection else ""

        self.name_tip_label.config(text="名称：")
        self.name_tip_label.grid_forget()
        self.name_tip_label.place(x=TkS(5), y=TkS(13))
        self.name_edit_entry.config(state=tk.NORMAL)
        self.name_edit_entry.delete(0, tk.END)
        self.name_edit_entry.insert(0, name)
        self.name_edit_entry.place(x=TkS(50), y=TkS(5), height=TkS(35), relwidth=0.8)
        self.detail_desc_text.config(state=tk.NORMAL)
        self.detail_desc_text.delete('1.0', tk.END)
        text = f"描述：{model_config.meta.description}\n\n下载地址：{model_config.meta.download_url}"
        self.detail_desc_text.insert(tk.END, text)
        self.detail_desc_text.place(relx=0.01, y=TkS(70), relwidth=0.98, relheight=0.7)
        self.detail_desc_text.config(state=tk.DISABLED)

        if status == STATUS_LABEL["not download"]:
            self.name_edit_entry.config(state=tk.DISABLED)
            self.download_btn.place(relx=0.5, rely=0.88, anchor=tk.CENTER, width=TkS(100), height=TkS(40))
        elif status == STATUS_LABEL["downloading"]:
            self.name_edit_entry.config(state=tk.DISABLED)
        else:
            self.use_btn.place(relx=0.32, rely=0.88, anchor=tk.CENTER, width=TkS(100), height=TkS(40))
            self.uninstall_btn.place(relx=0.68, rely=0.88, anchor=tk.CENTER, width=TkS(100), height=TkS(40))
            self.use_btn.config(state=tk.DISABLED if status == STATUS_LABEL["using"] else tk.NORMAL)
            self.uninstall_btn.config(state=tk.DISABLED if status == STATUS_LABEL["using"] else tk.NORMAL)

    def show_default(self) -> None:
        for w in (
            self.name_edit_entry, self.detail_desc_text, self.use_btn, self.uninstall_btn,
            self.download_btn, self.download_progressbar, self.download_progress_label,
            self.download_control_btn, self.download_cancel_btn,
        ):
            w.place_forget()
        self.name_tip_label.config(text="选择模型查看详细信息")
        self.name_tip_label.grid(row=0, column=0)

