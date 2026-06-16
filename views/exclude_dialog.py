"""Exclude rules management dialog — UI only. Control logic in ExcludePreviewController."""

from ttkbootstrap import Button, Style
from ttkbootstrap.constants import LINK
from tkinter.ttk import LabelFrame, Entry, Label, Treeview, Scrollbar
import tkinter as tk
from tkinter import filedialog

from settings import WinInfo


class ExcludeDialog(tk.Toplevel):
    """Modal dialog for managing exclusion rules and previewing their effect."""

    def __init__(self, parent, setting) -> None:
        super().__init__(parent)
        self.withdraw()
        self.setting = setting
        self.save_result: bool | None = None  # True=保存, None=取消
        # Lazy import to avoid circular dependency:
        # exclude_dialog → exclude_controller → app_controller → views
        from controllers.exclude_controller import ExcludePreviewController
        self.controller = ExcludePreviewController(self, setting)

        self.title("排除设置")
        self.iconbitmap(WinInfo.ico_path)
        win_w = WinInfo.TkS(620)
        win_h = WinInfo.TkS(520)
        self._ipady = max(4, win_h // 81)
        self._ipadx = max(4, win_h // 56)
        x = parent.winfo_rootx() + (parent.winfo_width() - win_w) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - win_h) // 2
        self.geometry(f"{win_w}x{win_h}+{x}+{y}")
        self.minsize(500, 400)
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self.controller.on_save)

        self._build_upper()
        self._build_lower()

        self.controller.load_rules_into_view()
        self.deiconify()

    # ── UI helpers for controller ─────────────────────────────────────

    def collect_rules(self) -> list[str]:
        rules: list[str] = []
        for child in self.rules_tree.get_children():
            text = self.rules_tree.item(child, "values")[0].strip()
            if text:
                rules.append(text)
        return rules

    def clear_preview_tree(self) -> None:
        self.preview_tree.delete(*self.preview_tree.get_children())

    def set_status(self, text: str) -> None:
        self.preview_status_var.set(text)

    def set_status_foreground(self, color: str) -> None:
        self.preview_status_label.configure(foreground=color)

    def reset_status_foreground(self) -> None:
        self.preview_status_label.configure(foreground="")

    def show_stop_button(self) -> None:
        self.stop_btn.pack(side=tk.RIGHT, padx=(10, 0))

    def hide_stop_button(self) -> None:
        self.stop_btn.pack_forget()

    def _build_upper(self) -> None:
        frame = LabelFrame(self, text="排除规则")
        frame.place(relx=0.04, rely=0.03, relwidth=0.92, relheight=0.40)

        btn_frame = tk.Frame(frame)
        btn_frame.pack(fill=tk.X, padx=4, pady=(6, 10))
        Button(btn_frame, text="新建规则", command=self._on_add_name,
               takefocus=False, cursor="hand2").pack(side=tk.LEFT, padx=(0, 10), ipadx=self._ipadx, ipady=self._ipady)
        Button(btn_frame, text="删除规则", command=self._on_delete_selected,
               takefocus=False, cursor="hand2").pack(side=tk.LEFT, ipadx=self._ipadx, ipady=self._ipady)
        Button(btn_frame, text="帮助文档", command=self.controller.open_help_doc,
               takefocus=False, cursor="hand2", style=LINK).pack(side=tk.RIGHT, padx=(15, 0))

        tree_frame = tk.Frame(frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=(4, 4))
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        self.rules_tree = Treeview(
            tree_frame, columns=("name",), show="",
            selectmode="browse", cursor="hand2"
        )
        self.rules_tree.column("name", stretch=True)
        self.rules_tree.grid(row=0, column=0, sticky=tk.NSEW)
        self.rules_tree.bind("<Double-Button-1>", self._on_item_double_click)
        self.rules_tree.bind("<<TreeviewSelect>>", self.controller.on_rule_select)

        scroll = Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.rules_tree.yview)
        scroll.grid(row=0, column=1, sticky=tk.NS)
        self.rules_tree.configure(yscrollcommand=scroll.set)

    def _build_lower(self) -> None:
        frame = LabelFrame(self, text="选择任意文件夹预览排除效果")
        frame.place(relx=0.04, rely=0.46, relwidth=0.92, relheight=0.53)

        path_frame = tk.Frame(frame)
        path_frame.pack(fill=tk.X, padx=4, pady=(0, 10))
        self.preview_path_var = tk.StringVar()
        self.preview_path_entry = Entry(path_frame, textvariable=self.preview_path_var)
        self.preview_path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4), ipady=self._ipady)
        self.browse_btn = Button(path_frame, text="浏览", command=self._on_browse_preview,
                                 takefocus=False, cursor="hand2")
        self.browse_btn.pack(side=tk.RIGHT, ipadx=self._ipadx * 2, ipady=self._ipady)

        status_frame = tk.Frame(frame)
        status_frame.pack(fill=tk.X, padx=4, pady=(0, 2))
        self.preview_status_var = tk.StringVar()
        self.preview_status_label = Label(status_frame, textvariable=self.preview_status_var, anchor=tk.W)
        self.preview_status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.stop_btn = Button(status_frame, text="停止", style=LINK, cursor="hand2",
                                command=self.controller.stop_scan)

        tree_frame = tk.Frame(frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=0)
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        self.preview_tree = Treeview(
            tree_frame, columns=("path",), show="", cursor="hand2"
        )
        self.preview_tree.column("path", stretch=False, width=3000)
        self.preview_tree.grid(row=0, column=0, sticky=tk.NSEW)
        self.preview_tree.bind("<Double-Button-1>", self.controller.on_preview_double_click)

        preview_scroll_v = Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.preview_tree.yview)
        preview_scroll_v.grid(row=0, column=1, sticky=tk.NS)
        preview_scroll_h = Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.preview_tree.xview)
        preview_scroll_h.grid(row=1, column=0, columnspan=2, sticky=tk.EW)
        self.preview_tree.configure(
            yscrollcommand=preview_scroll_v.set,
            xscrollcommand=preview_scroll_h.set
        )

    def _edit_item(self, iid: str, initial_text: str = "") -> None:
        if hasattr(self, '_rule_entry') and self._rule_entry and self._rule_entry.winfo_exists():
            self._rule_entry.destroy()

        tree = self.rules_tree
        tree.selection_remove(*tree.selection())
        parent = tree.master

        tree.update_idletasks()
        item_bbox = tree.bbox(iid, column="name")
        if item_bbox:
            ix, iy, _, ih = item_bbox
            entry_x = tree.winfo_x() + ix
            entry_y = tree.winfo_y() + iy
            entry_h = ih
        else:
            row_height = 50
            children = tree.get_children()
            row_idx = children.index(iid)
            entry_x = 2
            entry_y = row_idx * row_height + 2
            entry_h = row_height

        entry_w = tree.winfo_width()
        tv_font = Style().lookup("Treeview", "font") or "TkDefaultFont"

        entry = tk.Entry(parent, font=tv_font, bd=0, highlightthickness=1)
        entry.insert(0, initial_text)
        entry.select_range(0, tk.END)
        entry.icursor(tk.END)
        self._rule_entry = entry

        _confirming = False
        def on_confirm(event=None):
            nonlocal _confirming
            if _confirming:
                return
            _confirming = True
            text = entry.get().strip()
            if text:
                tree.item(iid, values=(text,))
                tree.selection_set(iid)
                tree.focus(iid)
                self.controller.refilter_preview()
            elif not initial_text:
                tree.delete(iid)
            entry.master.after_idle(entry.destroy)

        def on_cancel(event=None):
            nonlocal _confirming
            if _confirming:
                return
            _confirming = True
            if not initial_text:
                tree.delete(iid)
            entry.master.after_idle(entry.destroy)

        entry.place(x=entry_x, y=entry_y, width=entry_w, height=entry_h)
        entry.focus_set()
        entry.bind("<Return>", on_confirm)
        entry.bind("<FocusOut>", on_confirm)
        entry.bind("<Escape>", on_cancel)

    def _on_add_name(self) -> None:
        iid = self.rules_tree.insert("", tk.END, values=("",))
        self.rules_tree.yview_moveto(1.0)
        self._edit_item(iid, "")

    def _on_item_double_click(self, event: tk.Event) -> None:
        iid = self.rules_tree.identify_row(event.y)
        if not iid:
            return
        text = self.rules_tree.item(iid, "values")[0]
        self._edit_item(iid, text)

    def _on_delete_selected(self) -> None:
        selected = self.rules_tree.selection()
        if selected:
            self.rules_tree.delete(*selected)
            self.controller.refilter_preview()

    def _on_browse_preview(self) -> None:
        dir_path = filedialog.askdirectory(title="选择要预览的目录")
        if dir_path:
            self.preview_path_var.set(dir_path)
            self.controller.trigger_preview()

