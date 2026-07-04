from ttkbootstrap import Button, Entry, Frame, Label, LabelFrame, Progressbar, Treeview, Scrollbar
import tkinter as tk

from settings import WinInfo, ModelConfig, TkS


class ModelFrame(Frame):
    search_entry: Entry
    model_tree: Treeview
    detail_frame: LabelFrame
    local_model_frame: LabelFrame
    detail_name_entry: Entry
    detail_desc_text: tk.Text
    use_btn: Button
    uninstall_btn: Button
    download_btn: Button
    download_progressbar: Progressbar
    download_progress_label: Label
    local_path_entry: Entry
    local_browse_btn: Button
    local_parse_btn: Button
    local_share_btn: Button

    def __init__(self, parent, **kwargs) -> None:
        super().__init__(parent, **kwargs)

        model_list_frame = self.__set_model_list_frame()
        detail_frame = self.__set_detail_frame()
        local_model_frame = self.__set_local_model_frame()

        self.search_entry = self.__set_search_entry(model_list_frame)
        self.model_tree = self.__set_model_tree(model_list_frame)

        self.name_edit_frame = Frame(detail_frame)
        self.name_tip_label = Label(self.name_edit_frame, text="名称：")
        self.detail_name_entry = Entry(self.name_edit_frame)
        self.detail_desc_text = tk.Text(detail_frame, wrap='char')
        self.use_btn = Button(detail_frame, text="使用模型", takefocus=False, padding=(WinInfo.PX_15, WinInfo.PX_5))
        self.uninstall_btn = Button(detail_frame, text="卸载模型", takefocus=False, padding=(WinInfo.PX_15, WinInfo.PX_5), style="secondary")
        self.download_btn = Button(detail_frame, text="下载模型", takefocus=False, padding=(WinInfo.PX_15, WinInfo.PX_5))
        self.download_progressbar = Progressbar(detail_frame, orient=tk.HORIZONTAL, mode="determinate", maximum=100)
        self.download_progress_label = Label(detail_frame, text="")

        self.local_share_btn = Button(parent, text="分享模型到 GitHub Issue", cursor="hand2", padding=(TkS(10), WinInfo.PX_4), style="LINK")
        self.local_path_entry, self.local_browse_btn = self.__set_local_path_section(local_model_frame)
        self.local_parse_btn = self.__set_local_parse_button(local_model_frame)
        
        self.show_default()

    def __set_model_list_frame(self) -> LabelFrame:
        frame = LabelFrame(self, text="模型列表")
        frame.place(relx=0.01, rely=0.02, relwidth=0.57, relheight=0.98)
        return frame

    def __set_search_entry(self, parent) -> Entry:
        entry = Entry(parent, font=(WinInfo.default_font_family, WinInfo.default_font_size))
        entry.pack(side=tk.TOP, fill=tk.X, pady=(WinInfo.PX_5, WinInfo.PX_5), padx=WinInfo.PX_5, ipady=WinInfo.PX_5)
        return entry

    def __set_model_tree(self, parent) -> Treeview:
        columns = ["名称", "标签", "类型", "大小", "状态"]
        tree = Treeview(parent, show="headings", columns=columns)
        tree.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=WinInfo.PX_5)
        col_widths = {"名称": TkS(40), "标签": TkS(30), "类型": TkS(30), "大小": TkS(30), "状态": TkS(30)}
        for col in columns:
            tree.heading(col, text=col, anchor=tk.CENTER)
            tree.column(col, anchor=tk.CENTER, width=col_widths[col], stretch=True)
        scrollbar = Scrollbar(tree, orient=tk.VERTICAL, cursor="hand2")
        scrollbar.pack(fill=tk.BOTH, side=tk.RIGHT, pady=(WinInfo.PX_1, WinInfo.PX_1), padx=WinInfo.PX_1)
        scrollbar.config(command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        return tree

    def __set_detail_frame(self) -> LabelFrame:
        frame = LabelFrame(self, text="模型详情")
        frame.place(relx=0.59, rely=0.02, relwidth=0.40, relheight=0.66)
        return frame

    def __set_local_model_frame(self) -> LabelFrame:
        frame = LabelFrame(self, text="加载本地模型")
        frame.place(relx=0.59, rely=0.69, relwidth=0.40, relheight=0.29)
        return frame

    def __set_local_path_section(self, parent) -> tuple[Entry, Button]:
        container = Frame(parent)
        container.pack(fill=tk.X, padx=WinInfo.PX_5, pady=(WinInfo.PX_5, WinInfo.PX_2))
        path_entry = Entry(container)
        path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, WinInfo.PX_4), ipady=WinInfo.PX_5)
        browse_btn = Button(container, text="浏览")
        browse_btn.pack(side=tk.LEFT, ipadx=WinInfo.PX_15, ipady=WinInfo.PX_5)
        return path_entry, browse_btn

    def __set_local_parse_button(self, parent) -> Button:
        btn = Button(parent, text="解析模型", style="link", cursor="hand2")
        btn.pack(anchor=tk.CENTER, expand=True)
        return btn

    def set_detail(self, model_config: ModelConfig) -> None:
        for w in (self.name_edit_frame, self.name_tip_label, self.detail_name_entry,
                  self.detail_desc_text, self.use_btn, self.uninstall_btn,
                  self.download_btn, self.download_progress_label, self.download_progressbar):
            w.place_forget()

        selection = self.model_tree.selection()
        name = self.model_tree.item(selection[0], "values")[0] if selection else ""
        status = self.model_tree.item(selection[0], "values")[-1] if selection else ""

        self.name_edit_frame.place(relx=0.01, y=WinInfo.PX_5, height=TkS(35), relwidth=0.98)
        self.name_tip_label.config(text="名称：")
        self.name_tip_label.pack(side=tk.LEFT)
        self.detail_name_entry.delete(0, tk.END)
        self.detail_name_entry.insert(0, name)
        self.detail_name_entry.pack(fill=tk.BOTH, expand=True)

        self.detail_desc_text.delete('1.0', tk.END)
        text = f"{model_config.description}；模型下载地址：\n{model_config.download_url}"
        self.detail_desc_text.insert(tk.END, text)
        self.detail_desc_text.place(relx=0.01, y=TkS(45), relwidth=0.98, relheight=0.6)

        if status == "未下载":
            self.download_btn.place(relx=0.5, rely=0.88, anchor=tk.CENTER)
            self.download_progress_label.place(x=TkS(6), rely=0.95, anchor=tk.W)
            self.download_progressbar.place(relx=0.30, rely=0.95, relwidth=0.65)
        else:
            self.use_btn.place(relx=0.32, rely=0.88, anchor=tk.CENTER, width=TkS(100), height=TkS(40))
            self.uninstall_btn.place(relx=0.68, rely=0.88, anchor=tk.CENTER, width=TkS(100), height=TkS(40))
            self.use_btn.config(state=tk.DISABLED if status == "正在使用" else tk.NORMAL)
            self.uninstall_btn.config(state=tk.DISABLED if status == "正在使用" else tk.NORMAL)

    def show_default(self) -> None:
        for w in (self.name_edit_frame, self.name_tip_label, self.detail_name_entry,
                  self.detail_desc_text, self.use_btn, self.uninstall_btn,
                  self.download_btn, self.download_progressbar, self.download_progress_label):
            w.place_forget()
        self.local_share_btn.grid_forget()
        self.name_tip_label.config(text="选择模型查看详细信息")
        self.name_tip_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

    def set_download_progress(self, text: str) -> None:
        self.download_progress_label.config(text=text)
        if text.endswith("%"):
            try:
                value = int(text[:-1])
                self.download_progressbar.config(value=value)
            except ValueError:
                pass

    def set_action_buttons_enabled(self, enabled: bool) -> None:
        state = tk.NORMAL if enabled else tk.DISABLED
        for b in (self.use_btn, self.uninstall_btn, self.download_btn):
            b.config(state=state)
