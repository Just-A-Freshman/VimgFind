from __future__ import annotations

import tkinter as tk

from ttkbootstrap.constants import LINK
from ttkbootstrap import Button, Labelframe, Frame, Entry, Label, Treeview, Scrollbar

from config.settings import TkS
from views.widgets import simpledialog
from utils.i18n import _


class ExcludeDialog(simpledialog.SingletonDialog):
    add_rule_btn: Button
    del_rule_btn: Button
    help_btn: Button
    rules_tree: Treeview
    preview_path_entry: Entry
    browse_btn: Button
    preview_status_label: Label
    stop_btn: Button
    preview_tree: Treeview
    __slots__ = (
        "add_rule_btn", "del_rule_btn", "help_btn",
        "rules_tree", "preview_path_entry", "browse_btn",
        "preview_status_label", "stop_btn", "preview_tree"
    )

    def __init__(self, parent) -> None:
        if hasattr(self, '_initialized'):
            return
        super().__init__(parent, title=_("排除设置"), height=TkS(400))
        edit_rules_frame = self.__set_edit_rules_frame()
        button_frame = self.__set_edit_frame(edit_rules_frame)
        self.add_rule_btn = self.__set_add_rule_btn(button_frame)
        self.del_rule_btn = self.__set_del_rule_btn(button_frame)
        self.help_btn = self.__set_help_btn(button_frame)
        self.rules_tree = self.__set_rules_tree(edit_rules_frame)
        
        preview_rules_frame = self.__set_preview_rules_frame()
        path_frame = self.__set_edit_frame(preview_rules_frame)
        status_frame = self.__set_edit_frame(preview_rules_frame)
        self.preview_path_entry = self.__set_preview_path_entry(path_frame)
        self.browse_btn = self.__set_browse_btn(path_frame)
        self.preview_status_label = self.__set_preview_status_label(status_frame)
        self.stop_btn = Button(status_frame, text=_("停止"), style=LINK, cursor="hand2")
        self.preview_tree = self.__set_preview_tree(preview_rules_frame)

    def __set_edit_rules_frame(self) -> Labelframe:
        frame = Labelframe(self, text=_("排除规则"))
        frame.place(relx=0.02, rely=0.01, relwidth=0.96, relheight=0.45)
        return frame

    def __set_edit_frame(self, parent) -> Frame:
        btn_frame = Frame(parent)
        btn_frame.pack(fill=tk.X, padx=TkS(2), pady=(TkS(1), TkS(2)))
        return btn_frame

    def __set_rules_tree(self, parent) -> Treeview:
        rules_tree = Treeview(parent, columns=("name",), show="", selectmode="browse", cursor="hand2")
        rules_tree.column("name", stretch=True)
        rules_tree.pack(fill=tk.BOTH, expand=True, padx=TkS(2), pady=(0, TkS(1)))
        scroll = Scrollbar(rules_tree, orient=tk.VERTICAL, command=rules_tree.yview)
        scroll.pack(fill=tk.Y, side=tk.RIGHT, padx=TkS(1), pady=TkS(1))
        rules_tree.configure(yscrollcommand=scroll.set)
        return rules_tree

    def __set_add_rule_btn(self, parent: Frame) -> Button:
        add_rule_btn = Button(parent, text=_("新建"), takefocus=False, cursor="hand2")
        add_rule_btn.pack(side=tk.LEFT, padx=(0, TkS(5)), ipadx=TkS(6))
        return add_rule_btn

    def __set_del_rule_btn(self, parent: Frame) -> Button:
        del_rule_btn = Button(parent, text=_("删除"), takefocus=False, cursor="hand2")
        del_rule_btn.pack(side=tk.LEFT, ipadx=TkS(6))
        return del_rule_btn

    def __set_help_btn(self, parent: Frame) -> Button:
        help_btn = Button(parent, text=_("帮助文档"), takefocus=False, cursor="hand2", style=LINK)
        help_btn.pack(side=tk.RIGHT, padx=(TkS(6), 0))
        return help_btn

    def __set_preview_rules_frame(self) -> Labelframe:
        frame = Labelframe(self, text=_("选择任意文件夹预览排除效果"))
        frame.place(relx=0.02, rely=0.48, relwidth=0.96, relheight=0.52)
        return frame

    def __set_preview_path_entry(self, parent: Frame) -> Entry:
        preview_path_entry = Entry(parent)
        preview_path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, TkS(2)))
        return preview_path_entry

    def __set_browse_btn(self, parent: Frame) -> Button:
        browse_btn = Button(parent, text=_("浏览"), takefocus=False, cursor="hand2")
        browse_btn.pack(side=tk.RIGHT, ipadx=TkS(6))
        return browse_btn

    def __set_preview_status_label(self, parent: Frame) -> Label:
        preview_status_label = Label(parent, anchor=tk.W)
        preview_status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        return preview_status_label

    def __set_preview_tree(self, parent: Labelframe) -> Treeview:
        preview_tree = Treeview(parent, columns=("path",), show="", cursor="hand2")
        preview_tree.column("path", stretch=False, width=0)
        preview_tree.pack(fill=tk.BOTH, expand=True, padx=TkS(2))

        preview_scroll_v = Scrollbar(preview_tree, orient=tk.VERTICAL, command=preview_tree.yview)
        preview_scroll_v.pack(fill=tk.Y, side=tk.RIGHT, padx=(0, TkS(1)), pady=TkS(1))
        preview_scroll_h = Scrollbar(preview_tree, orient=tk.HORIZONTAL, command=preview_tree.xview)
        preview_scroll_h.pack(fill=tk.X, side=tk.BOTTOM, padx=(TkS(1), 0), pady=TkS(1))
        preview_tree.configure(yscrollcommand=preview_scroll_v.set, xscrollcommand=preview_scroll_h.set)
        return preview_tree
