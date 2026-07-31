from __future__ import annotations

from dataclasses import dataclass
import tkinter as tk

from ttkbootstrap import Button, Frame, Label, Labelframe, Treeview, Text, Scrollbar
from ttkbootstrap.constants import LINK

from config.settings import WinInfo, TkS
from config.types import MenuItemDef
from utils.i18n import _


@dataclass
class TestResultItem:
    file_name: str
    resolved_cmd: list[str]
    returncode: int
    stdout: str
    stderr: str
    time_consuming: float


class TestResultDialog(tk.Toplevel):
    def __init__(self, parent, results: list[TestResultItem], menu_item: MenuItemDef) -> None:
        super().__init__(parent)
        self.withdraw()
        self.__results = results
        self.__menu_items = menu_item
        self.open_tempdir_btn = self.__set_summary_bar()
        self.file_tree = self.__set_execution_list()
        self.detail_text, self.copy_btn = self.__set_detail_panel()
        self.__win(parent)

    def __win(self, parent) -> None:
        self.transient(parent)
        self.title(_("命令测试结果"))
        self.iconbitmap(WinInfo.ico_path)
        win_w = TkS(480)
        win_h = TkS(400)
        x = parent.winfo_rootx() + (parent.winfo_width() - win_w) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - win_h) // 2
        self.geometry(f"{win_w}x{win_h}+{x}+{y}")
        self.transient(parent)
        self.minsize(TkS(400), TkS(320))
        self.deiconify()

    def __set_summary_bar(self) -> Button:
        bar = Frame(self)
        bar.pack(fill=tk.X, padx=TkS(10), pady=(TkS(8), 0))
        success = sum(1 for r in self.__results if r.returncode == 0)
        failed = len(self.__results) - success
        time_consuming = self.__results[0].time_consuming if self.__menu_items.batch_mode else sum(i.time_consuming for i in self.__results)
        open_btn = Button(bar, text=_("打开临时文件夹"), style=LINK, cursor="hand2", takefocus=False,)
        open_btn.pack(side=tk.RIGHT)
        summary = Label(bar, text=_(
            "共{total}条  成功: {ok}  失败: {fail}，耗时：{time_consuming:.3f}s",
            total=len(self.__results), ok=success, fail=failed, time_consuming=time_consuming),
            font=(WinInfo.default_font_family, WinInfo.default_font_size, "bold")
        )
        summary.pack(side=tk.LEFT)
        return open_btn

    def __set_execution_list(self) -> Treeview:
        column_info = (("status", "", TkS(40)), ("filename", _("副本文件"), TkS(300)), ("retcode", _("返回码"), TkS(60)))
        tree = Treeview(self, columns=[i[0] for i in column_info], show="headings", selectmode="browse", cursor="hand2", height=4)
        for i, (column, text, width) in enumerate(column_info):
            tree.heading(column, text=text, anchor=tk.CENTER)
            tree.column(column, width=width, stretch=i == 1, anchor=tk.W if i == 1 else tk.CENTER)
        tree.pack(fill=tk.X, padx=TkS(10), pady=(TkS(6), 0))
        if self.__results:
            for i, r in enumerate(self.__results):
                tree.insert("", tk.END, iid=str(i), values=("✓" if r.returncode == 0 else "✗", r.file_name, r.returncode))
            tree.selection_set(0)
        return tree

    def __set_detail_panel(self) -> tuple[tk.Text, Button]:
        frame = Labelframe(self, text=_("命令详情"))
        frame.pack(fill=tk.BOTH, expand=True, pady=(TkS(6), TkS(8)))
        text = Text(
            frame, wrap=tk.CHAR, height=8, font=(WinInfo.default_font_family, WinInfo.default_font_size),
            state=tk.DISABLED, relief=tk.FLAT, borderwidth=0, padx=TkS(1), pady=TkS(4),
        )
        text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = Scrollbar(text, orient=tk.VERTICAL, command=text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        text.config(yscrollcommand=scrollbar.set)
        copy_btn = Button(text, text=_("复制"), style="inner.Link.TButton", takefocus=False, cursor="hand2")
        copy_btn.pack(side=tk.BOTTOM, anchor=tk.SE)
        copy_btn.bind("<ButtonRelease-1>", lambda e: copy_btn.config(text="✓") or self.after(1000, lambda: copy_btn.config(text=_("复制"))))
        return text, copy_btn

    def show_result(self) -> None:
        selection = self.file_tree.selection()
        if not selection:
            return
        r = self.__results[int(selection[0])]
        params_block = "\n" + "\n".join(f"  [{i}] {arg}" for i, arg in enumerate(r.resolved_cmd[1:], start=1)) if len(r.resolved_cmd) > 1 else _("无参数")
        show_execute = f"{_('命令本体')}: {r.resolved_cmd[0]}\n{_('参数清单')}: {params_block}"
        text = (
            f"{_('[原始模板]')}\n{self.__menu_items.command}\n\n"
            f"{_('[解析结果]')}\n{show_execute}\n\n"
            f"{_('[标准输出]')}\n{r.stdout or _('(无输出)')}\n\n"
            f"{_('[错误输出]')}\n{r.stderr or _('(无输出)')}"
        )
        if text.strip() == self.detail_text.get("1.0", tk.END).strip():
            return
        self.detail_text.config(state=tk.NORMAL)
        self.detail_text.delete("1.0", tk.END)
        self.detail_text.insert("1.0", text)
        self.detail_text.config(state=tk.DISABLED)
