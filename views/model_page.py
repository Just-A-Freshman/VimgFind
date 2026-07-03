from ttkbootstrap import Button, Frame, LabelFrame, Treeview, Scrollbar
import tkinter as tk
from typing import Literal


class ModelFrame(Frame):
    model_tree: Treeview
    detail_frame: LabelFrame
    detail_text: tk.Text
    use_btn: Button
    uninstall_btn: Button
    download_btn: Button
    download_progress: tk.Label

    def __init__(self, parent, **kwargs) -> None:
        super().__init__(parent, **kwargs)
        self.place(relx=0, rely=0, relwidth=1, relheight=1)

        self.model_tree = self.__set_model_tree()
        self.detail_frame = self.__set_detail_frame()
        self.detail_text = self.__set_detail_text()
        self.use_btn, self.uninstall_btn, self.download_btn = self.__set_action_buttons()
        self.show_default()

    def __set_model_tree(self) -> Treeview:
        columns = ["名称", "标签", "类型", "大小", "状态"]
        tree = Treeview(self, show="headings", columns=columns)
        tree.place(relx=0.01, rely=0.02, relwidth=0.54, relheight=0.96)
        col_widths = {"名称": 60, "标签": 60, "类型": 60, "大小": 60, "状态": 80}
        for col in columns:
            tree.heading(col, text=col, anchor=tk.CENTER)
            tree.column(col, anchor=tk.CENTER, width=col_widths[col], stretch=True)
        scrollbar = Scrollbar(tree, orient=tk.VERTICAL, cursor="hand2")
        scrollbar.pack(fill=tk.BOTH, side=tk.RIGHT, pady=(2, 2), padx=2)
        scrollbar.config(command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        return tree

    def __set_detail_frame(self) -> LabelFrame:
        frame = LabelFrame(self, text="模型详情")
        frame.place(relx=0.56, rely=0.02, relwidth=0.43, relheight=0.96)
        return frame

    def __set_detail_text(self) -> tk.Text:
        text = tk.Text(self.detail_frame, wrap=tk.WORD, relief=tk.FLAT, state=tk.DISABLED)
        text.pack(fill=tk.BOTH, expand=True, padx=8, pady=(8, 4))
        return text

    def __set_action_buttons(self) -> tuple[Button, Button, Button]:
        btn_frame = Frame(self.detail_frame)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=(4, 12))
        center = Frame(btn_frame)
        center.pack(anchor=tk.CENTER)
        use_btn = Button(center, text="使用模型", takefocus=False, cursor="hand2", padding=(16, 6))
        use_btn.pack(side=tk.LEFT, padx=(0, 16))
        uninstall_btn = Button(
            center, text="卸载模型", takefocus=False,
            cursor="hand2", padding=(16, 6), style="secondary",
        )
        uninstall_btn.pack(side=tk.LEFT, padx=(0, 16))
        download_btn = Button(center, text="下载模型", takefocus=False, cursor="hand2", padding=(16, 6))
        download_btn.pack(side=tk.LEFT)
        self.download_progress = tk.Label(center, text="", fg="gray")
        self.download_progress.pack(side=tk.LEFT, padx=(8, 0))
        for b in (use_btn, uninstall_btn, download_btn):
            b.pack_forget()
        return use_btn, uninstall_btn, download_btn

    def set_model_data(self, data: list[tuple[str, str, str, str, str]]) -> None:
        self.model_tree.delete(*self.model_tree.get_children())
        for item in data:
            self.model_tree.insert("", tk.END, values=item)

    def set_detail(self, description: str, status: Literal["using", "downloaded", "not download"]) -> None:
        self.detail_text.config(state=tk.NORMAL)
        self.detail_text.delete("1.0", tk.END)
        self.detail_text.insert("1.0", description)
        self.detail_text.config(state=tk.DISABLED)
        for b in (self.use_btn, self.uninstall_btn, self.download_btn):
            b.pack_forget()
        if status == "using":
            self.use_btn.config(state=tk.DISABLED)
            self.uninstall_btn.config(state=tk.DISABLED)
            self.use_btn.pack(side=tk.LEFT, padx=(0, 16))
            self.uninstall_btn.pack(side=tk.LEFT)
        elif status == "downloaded":
            self.use_btn.config(state=tk.NORMAL)
            self.uninstall_btn.config(state=tk.NORMAL)
            self.use_btn.pack(side=tk.LEFT, padx=(0, 16))
            self.uninstall_btn.pack(side=tk.LEFT)
        else:
            self.download_btn.pack(side=tk.LEFT)

    def show_default(self) -> None:
        self.detail_text.config(state=tk.NORMAL)
        self.detail_text.delete("1.0", tk.END)
        self.detail_text.insert("1.0", "选择模型查看详细信息")
        self.detail_text.config(state=tk.DISABLED)
        for b in (self.use_btn, self.uninstall_btn, self.download_btn):
            b.pack_forget()
        self.download_progress.config(text="")

    def set_download_progress(self, text: str) -> None:
        self.download_progress.config(text=text)

    def set_action_buttons_enabled(self, enabled: bool) -> None:
        state = tk.NORMAL if enabled else tk.DISABLED
        for b in (self.use_btn, self.uninstall_btn, self.download_btn):
            b.config(state=state)

