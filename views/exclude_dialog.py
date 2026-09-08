from __future__ import annotations

import tkinter as tk

from ttkbootstrap.constants import LINK
from ttkbootstrap import Button, Labelframe, Frame, Treeview, Scrollbar

from config.settings import TkS
from views.widgets import simpledialog
from utils.i18n import _


class ExcludeDialog(simpledialog.SingletonDialog):
    add_rule_btn: Button
    del_rule_btn: Button
    help_btn: Button
    rules_tree: Treeview
    __slots__ = ("add_rule_btn", "del_rule_btn", "help_btn", "rules_tree")

    def __init__(self, parent) -> None:
        if hasattr(self, '_initialized'):
            return
        super().__init__(parent, title=_("排除设置"), height=TkS(400))
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        edit_rules_frame = self.__set_edit_rules_frame()
        button_frame = self.__set_edit_frame(edit_rules_frame)
        self.add_rule_btn = self.__set_add_rule_btn(button_frame)
        self.del_rule_btn = self.__set_del_rule_btn(button_frame)
        self.help_btn = self.__set_help_btn(button_frame)
        self.rules_tree = self.__set_rules_tree(edit_rules_frame)

    def __set_edit_rules_frame(self) -> Labelframe:
        frame = Labelframe(self, text=_("排除规则"))
        frame.grid(row=0, column=0, sticky=tk.NSEW, padx=TkS(5), pady=TkS(5))
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
