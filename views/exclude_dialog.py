from ttkbootstrap import Button, Style
from ttkbootstrap.constants import LINK
from tkinter.ttk import LabelFrame, Entry, Label, Treeview, Scrollbar
import tkinter as tk
from tkinter import filedialog
from threading import Thread
from pathlib import Path
import os

import pathspec
from pathspec.patterns.gitwildmatch import GitWildMatchPattern

from config import WinInfo
from utils import FileOperation
from utils.exclude_rules import compile_rules, is_accepted_extension


MAX_PREVIEW_ITEMS = 50000
PROGRESS_INTERVAL = 500


class ExcludeDialog(tk.Toplevel):
    def __init__(self, parent, setting) -> None:
        super().__init__(parent)
        self.withdraw()
        self.setting = setting
        self.result: bool | None = None  # True=保存, None=取消
        self._original_rules: list[str] = []

        self._cancel_scan = False
        self._scan_thread: Thread | None = None
        self._hint_timer: str | None = None
        self._hint_original_title = "排除设置"
        self._preview_cache: list[tuple[str, bool]] = []  # (rel_path, is_dir)
        self._preview_total = 0
        self._preview_excluded = 0
        self._debounce_timer: str | None = None

        self.title(self._hint_original_title)
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
        self.protocol("WM_DELETE_WINDOW", self._on_save)

        self._build_upper()
        self._build_lower()

        self._load_rules()
        self.deiconify()

    def _build_upper(self) -> None:
        frame = LabelFrame(self, text="排除规则")
        frame.place(relx=0.04, rely=0.03, relwidth=0.92, relheight=0.40)

        btn_frame = tk.Frame(frame)
        btn_frame.pack(fill=tk.X, padx=4, pady=(6, 10))
        Button(btn_frame, text="新建规则", command=self._on_add_name,
               takefocus=False, cursor="hand2").pack(side=tk.LEFT, padx=(0, 10), ipadx=self._ipadx, ipady=self._ipady)
        Button(btn_frame, text="删除规则", command=self._on_delete_selected,
               takefocus=False, cursor="hand2").pack(side=tk.LEFT, ipadx=self._ipadx, ipady=self._ipady)
        Button(btn_frame, text="帮助文档", command=self._open_help_doc,
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
        self.rules_tree.bind("<<TreeviewSelect>>", self._on_rule_select)

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

        # Status bar: progress text + stop button
        status_frame = tk.Frame(frame)
        status_frame.pack(fill=tk.X, padx=4, pady=(0, 2))
        self.preview_status_var = tk.StringVar()
        self.preview_status_label = Label(status_frame, textvariable=self.preview_status_var, anchor=tk.W)
        self.preview_status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.stop_btn = Button(status_frame, text="停止", style=LINK, cursor="hand2",
                                command=self._stop_scan)

        tree_frame = tk.Frame(frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=0)
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        self.preview_tree = Treeview(
            tree_frame, columns=("path",), show="",
            cursor="hand2"
        )
        self.preview_tree.column("path", stretch=True)
        self.preview_tree.grid(row=0, column=0, sticky=tk.NSEW)
        self.preview_tree.bind("<Double-Button-1>", self._on_preview_double_click)

        preview_scroll_v = Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.preview_tree.yview)
        preview_scroll_v.grid(row=0, column=1, sticky=tk.NS)
        preview_scroll_h = Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.preview_tree.xview)
        preview_scroll_h.grid(row=1, column=0, columnspan=2, sticky=tk.EW)
        self.preview_tree.configure(
            yscrollcommand=preview_scroll_v.set,
            xscrollcommand=preview_scroll_h.set
        )

    def _open_help_doc(self) -> None:
        doc_path = Path(__file__).parent / "docs" / "exclude_rules.md"
        FileOperation.open_file(doc_path)

    def _load_rules(self) -> None:
        rules: list[str] = self.setting.get_config("index", "exclude_rules") or []
        self._original_rules = list(rules)
        for rule in rules:
            self.rules_tree.insert("", tk.END, values=(rule,))
        self.preview_status_var.set("被排除索引的文件夹/文件")

    def _rules_changed(self) -> bool:
        current = self._collect_rules()
        return current != self._original_rules

    def _collect_rules(self) -> list[str]:
        rules: list[str] = []
        for child in self.rules_tree.get_children():
            text = self.rules_tree.item(child, "values")[0].strip()
            if text:
                rules.append(text)
        return rules

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
                self._trigger_preview()
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
            self._trigger_preview()

    def _on_rule_select(self, event: tk.Event) -> None:
        """Debounced 500ms refresh when a rule is selected."""
        if self._debounce_timer:
            self.after_cancel(self._debounce_timer)
        self._debounce_timer = self.after(500, self._refresh_preview_from_cache)

    def _stop_scan(self) -> None:
        self._cancel_scan = True

    # ── Preview scanning ──────────────────────────────────────────────

    def _trigger_preview(self) -> None:
        self._cancel_scan = True
        self.stop_btn.pack(side=tk.RIGHT, padx=(10, 0))
        self._preview_cache.clear()
        self._preview_total = 0
        self._preview_excluded = 0

        dir_path = self.preview_path_var.get().strip()
        if not dir_path or not Path(dir_path).is_dir():
            self.stop_btn.pack_forget()
            return

        self.preview_tree.delete(*self.preview_tree.get_children())
        self.preview_status_var.set("正在扫描目录结构...（点击停止终止扫描）")

        rules = self._collect_rules()
        if not rules:
            self.preview_status_var.set("被排除索引的文件夹/文件")
            self.stop_btn.pack_forget()
            return

        self._cancel_scan = False
        self._scan_thread = Thread(
            target=self._do_preview, args=(dir_path, rules), daemon=True
        )
        self._scan_thread.start()

    def _do_preview(self, target_dir: str, rules: list[str]) -> None:
        rules_obj = compile_rules(rules)
        if not rules_obj:
            self.after(0, self._preview_empty)
            return

        cache: list[tuple[str, bool]] = []
        total = 0
        excluded = 0
        truncated = False

        def _walk(path: str) -> None:
            nonlocal total, excluded, truncated
            try:
                with os.scandir(path) as it:
                    for entry in it:
                        if self._cancel_scan or truncated:
                            return

                        rel = os.path.relpath(entry.path, target_dir).replace("\\", "/")
                        total += 1

                        if entry.is_dir(follow_symlinks=False):
                            if rules_obj.is_excluded(rel, is_dir=True):
                                cache.append((rel, True))
                                excluded += 1
                                if excluded >= MAX_PREVIEW_ITEMS:
                                    truncated = True
                                    return
                            _walk(entry.path)
                        elif entry.is_file(follow_symlinks=False):
                            if not is_accepted_extension(entry.name):
                                continue
                            if rules_obj.is_excluded(rel, is_dir=False):
                                cache.append((rel, False))
                                excluded += 1
                                if excluded >= MAX_PREVIEW_ITEMS:
                                    truncated = True
                                    return

                        if total % PROGRESS_INTERVAL == 0:
                            self.after(0, lambda t=total, e=excluded: self._update_status(t, e))
            except PermissionError:
                pass

        _walk(target_dir)

        if not self._cancel_scan:
            self.after(0, lambda: self._preview_complete(cache, total, excluded, truncated))

    def _update_status(self, total: int, excluded: int) -> None:
        self.preview_status_var.set(
            f"已排除 {excluded} 项（共扫描 {total} 项）"
        )

    def _preview_empty(self) -> None:
        self.stop_btn.pack_forget()
        self.preview_status_var.set("被排除索引的文件夹/文件")

    def _preview_complete(self, cache, total, excluded, truncated) -> None:
        self._preview_cache = cache
        self._preview_total = total
        self._preview_excluded = excluded

        self.stop_btn.pack_forget()
        self.preview_status_label.configure(foreground="")

        if truncated:
            self.preview_status_var.set(
                f"排除项过多，仅展示前 {MAX_PREVIEW_ITEMS} 条，建议缩小预览范围"
            )
        else:
            self.preview_status_var.set(f"被排除索引的文件夹/文件（共 {excluded} 项）")

        # Check if all files excluded
        all_excluded = excluded > 0 and excluded >= total
        if all_excluded and not truncated:
            self.preview_status_var.set("⚠️ 当前规则排除了所有文件，索引结果为空")
            self.preview_status_label.configure(foreground="red")

        self._refresh_preview_tree()

    def _refresh_preview_from_cache(self) -> None:
        """Re-filter preview tree from cache (triggered by rule selection)."""
        if not self._preview_cache:
            return
        self._refresh_preview_tree()

    def _refresh_preview_tree(self) -> None:
        """Populate preview tree from cache, applying rule filter if a rule is selected."""
        selected = self.rules_tree.selection()
        filtered = self._preview_cache

        if selected:
            rule_text = self.rules_tree.item(selected[0], "values")[0].strip()
            if rule_text.startswith("!"):
                self.preview_tree.delete(*self.preview_tree.get_children())
                self.preview_status_var.set("取反规则本身不排除文件")
                return
            try:
                single_spec = pathspec.PathSpec.from_lines(
                    GitWildMatchPattern,
                    [rule_text.lower()],
                )
                filtered = [
                    (rel, is_dir) for rel, is_dir in self._preview_cache
                    if single_spec.match_file(
                        rel.lower() + ("/" if is_dir else "")
                    )
                ]
            except Exception:
                filtered = self._preview_cache

        # Populate treeview
        self.preview_tree.delete(*self.preview_tree.get_children())
        for rel, is_dir in filtered:
            prefix = "\U0001f4c2" if is_dir else "\U0001f4c4"  # 📂 / 📄
            self.preview_tree.insert("", tk.END, values=(prefix + rel,))

        if not selected:
            if self._preview_excluded >= self._preview_total > 0:
                self.preview_status_label.configure(foreground="red")
                self.preview_status_var.set("⚠️ 当前规则排除了所有文件，索引结果为空")

    def _on_browse_preview(self) -> None:
        dir_path = filedialog.askdirectory(title="选择要预览的目录")
        if dir_path:
            self.preview_path_var.set(dir_path)
            self._trigger_preview()

    def _on_preview_double_click(self, event: tk.Event) -> None:
        item = self.preview_tree.identify_row(event.y)
        if not item:
            return
        raw = self.preview_tree.item(item, "values")[0].strip()
        # Remove the leading emoji (first character) to get the path
        path = raw[1:] if len(raw) > 1 else raw
        preview_dir = self.preview_path_var.get().strip()
        if preview_dir and path:
            full_path = os.path.join(preview_dir, path)
            if Path(full_path).exists():
                FileOperation.open_file(full_path)

    def _on_save(self) -> None:
        self._cancel_scan = True
        rules = self._collect_rules()
        self.setting.modity_config("index", "exclude_rules", rules)
        self.setting.save_settings()
        self.result = True

        if self._rules_changed():
            if self._hint_timer:
                self.after_cancel(self._hint_timer)
            self.title("排除规则已更新，点击[设置]>[清理排除项]清理已索引文件")
            self._hint_timer = self.after(5000, self._finish_save)
        else:
            self.destroy()

    def _finish_save(self) -> None:
        self._hint_timer = None
        self.title(self._hint_original_title)
        self.destroy()
