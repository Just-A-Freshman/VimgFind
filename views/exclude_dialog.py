from ttkbootstrap import Button, LabelFrame, Frame, Entry, Label, Treeview, Scrollbar
from ttkbootstrap.constants import LINK
import tkinter as tk

from settings import WinInfo, TkS


class ExcludeDialog(tk.Toplevel):
    add_rule_btn: Button
    del_rule_btn: Button
    help_btn: Button
    rules_tree: Treeview
    preview_path_entry: Entry
    browse_btn: Button
    preview_status_label: Label
    stop_btn: Button
    preview_tree: Treeview

    def __init__(self, parent, setting) -> None:
        super().__init__(parent)
        self.parent = parent
        self.setting = setting
        self.__win()
        edit_rules_frame = self.__set_edit_rules_frame()
        button_frame = self.__set_edit_frame(edit_rules_frame)
        self.add_rule_btn = self.__set_add_rule_btn(button_frame)
        self.del_rule_btn = self.__set_del_rule_btn(button_frame)
        self.help_btn = self.__set_help_btn(button_frame)
        self.rules_tree = self.__set_rules_tree(edit_rules_frame)
        
        preview_rules_frame = self.__set_preview_rules_frame()
        path_frame = self.__set_edit_frame(preview_rules_frame)
        self.preview_path_entry = self.__set_preview_path_entry(path_frame)
        self.browse_btn = self.__set_browse_btn(path_frame)
        self.status_frame = self.__set_edit_frame(preview_rules_frame)
        self.preview_status_label = self.__set_preview_status_label(self.status_frame)
        self.stop_btn = self.__set_stop_btn(self.status_frame)
        self.preview_tree = self.__set_preview_tree(preview_rules_frame)

    def __win(self) -> None:
        self.withdraw()
        self.title("排除设置")
        self.iconbitmap(WinInfo.ico_path)
        win_w = TkS(620)
        win_h = TkS(520)
        self._ipady = max(4, win_h // 81)
        self._ipadx = max(4, win_h // 56)
        x = self.parent.winfo_rootx() + (self.parent.winfo_width() - win_w) // 2
        y = self.parent.winfo_rooty() + (self.parent.winfo_height() - win_h) // 2
        self.geometry(f"{win_w}x{win_h}+{x}+{y}")
        self.transient(self.parent)
        self.grab_set()
        self.deiconify()

    def __set_edit_rules_frame(self) -> LabelFrame:
        frame = LabelFrame(self, text="排除规则")
        frame.place(relx=0.04, rely=0.03, relwidth=0.92, relheight=0.40)
        return frame

    def __set_edit_frame(self, parent) -> Frame:
        btn_frame = Frame(parent)
        btn_frame.pack(fill=tk.X, padx=TkS(2), pady=(TkS(1), TkS(5)))
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
        add_rule_btn = Button(parent, text="新建规则", takefocus=False, cursor="hand2")
        add_rule_btn.pack(side=tk.LEFT, padx=(0, TkS(5)), ipadx=self._ipadx, ipady=self._ipady)
        return add_rule_btn

    def __set_del_rule_btn(self, parent: Frame) -> Button:
        del_rule_btn = Button(parent, text="删除规则", takefocus=False, cursor="hand2")
        del_rule_btn.pack(side=tk.LEFT, ipadx=self._ipadx, ipady=self._ipady)
        return del_rule_btn

    def __set_help_btn(self, parent: Frame) -> Button:
        help_btn = Button(parent, text="帮助文档", takefocus=False, cursor="hand2", style=LINK)
        help_btn.pack(side=tk.RIGHT, padx=(TkS(7), 0))
        return help_btn

    def __set_preview_rules_frame(self) -> LabelFrame:
        frame = LabelFrame(self, text="选择任意文件夹预览排除效果")
        frame.place(relx=0.04, rely=0.46, relwidth=0.92, relheight=0.53)
        return frame

    def __set_preview_path_entry(self, parent: Frame) -> Entry:
        preview_path_entry = Entry(parent, font=(WinInfo.default_font_family, WinInfo.default_font_size))
        preview_path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, TkS(2)), ipady=self._ipady)
        return preview_path_entry

    def __set_browse_btn(self, parent: Frame) -> Button:
        browse_btn = Button(parent, text="浏览", takefocus=False, cursor="hand2")
        browse_btn.pack(side=tk.RIGHT, ipadx=self._ipadx * 2, ipady=self._ipady)
        return browse_btn

    def __set_preview_status_label(self, parent: Frame) -> Label:
        preview_status_label = Label(parent, anchor=tk.W)
        preview_status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        return preview_status_label

    def __set_stop_btn(self, parent: Frame) -> Button:
        stop_btn = Button(parent, text="停止", style=LINK, cursor="hand2")
        return stop_btn

    def __set_preview_tree(self, parent: LabelFrame) -> Treeview:
        preview_tree = Treeview(parent, columns=("path",), show="", cursor="hand2")
        preview_tree.column("path", stretch=False, width=TkS(1500))
        preview_tree.pack(fill=tk.BOTH, expand=True, padx=TkS(2))

        preview_scroll_v = Scrollbar(preview_tree, orient=tk.VERTICAL, command=preview_tree.yview)
        preview_scroll_v.pack(fill=tk.Y, side=tk.RIGHT, padx=TkS(1), pady=TkS(1))
        preview_scroll_h = Scrollbar(preview_tree, orient=tk.HORIZONTAL, command=preview_tree.xview)
        preview_scroll_h.pack(fill=tk.X, side=tk.BOTTOM, padx=(TkS(1), 0), pady=TkS(1))
        preview_tree.configure(yscrollcommand=preview_scroll_v.set, xscrollcommand=preview_scroll_h.set)
        return preview_tree
