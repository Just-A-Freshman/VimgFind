from __future__ import annotations

from pathlib import Path
from threading import Thread
from tkinter import filedialog
import tkinter as tk
import logging
import os

from pathspec.patterns.gitwildmatch import GitWildMatchPattern
from pathspec import PathSpec
from ttkbootstrap import Style

from config import Setting, TkS
from utils.i18n import _
from views.exclude_dialog import ExcludeDialog
import utils.exclude_rules as exclude_rules
import utils.file_ops as file_ops

MAX_PREVIEW_ITEMS = 100000
PROGRESS_INTERVAL = 500


class ExcludePreviewController:
    def __init__(self, dialog: ExcludeDialog, setting: Setting) -> None:
        self.dialog = dialog
        self.setting = setting
        self._original_rules: list[str] = (self.setting.model.index.exclude_rules or [])
        self._cancel_scan = False
        self._scan_thread: Thread | None = None
        self._preview_cache: list[tuple[str, bool]] = []
        self._scan_cache: list[tuple[str, bool]] = []
        self._preview_total = 0
        self._preview_excluded = 0
        self._debounce_timer: str | None = None
        self._rule_entry = None
        self._closed = False
        self._preview_truncated = False
        self._edit_lock = False

    def collect_rules(self) -> list[str]:
        rules: list[str] = []
        for child in self.dialog.rules_tree.get_children():
            text = self.dialog.rules_tree.item(child, "values")[0].strip()
            if text:
                rules.append(text)
        return rules

    def on_rule_select(self, event=None) -> None:
        if self._debounce_timer is not None:
            self.dialog.after_cancel(self._debounce_timer)
        self._debounce_timer = self.dialog.after(500, self._refresh_preview_tree)

    def _compute_excluded(
        self,
        scan_cache: list[tuple[str, bool]],
        excl_rules,
        target_dir: str,
        max_items: int = MAX_PREVIEW_ITEMS,
    ) -> tuple[list[tuple[str, bool]], int, bool]:
        """对 scan_cache 应用 excl_rules，返回（被排除列表, 排除数, 是否截断）"""
        excluded: list[tuple[str, bool]] = []
        count = 0
        truncated = False
        for rel, is_dir in scan_cache:
            if count >= max_items:
                truncated = True
                break
            full_path = os.path.join(target_dir, rel)
            if is_dir:
                if excl_rules.should_skip_dir(full_path, target_dir):
                    excluded.append((rel, True))
                    count += 1
            else:
                if excl_rules.should_skip_file(full_path, target_dir):
                    excluded.append((rel, False))
                    count += 1
        return excluded, count, truncated

    def stop_scan(self) -> None:
        self._cancel_scan = True

    def on_delete_selected(self) -> None:
        selected = self.dialog.rules_tree.selection()
        if selected:
            self.dialog.rules_tree.delete(*selected)
            self.refilter_preview()

    def on_browse(self) -> None:
        dir_path = filedialog.askdirectory(title=_("选择要预览的目录"))
        if dir_path:
            self.dialog.preview_path_entry.delete(0, tk.END)
            self.dialog.preview_path_entry.insert(tk.END, dir_path)
            self.trigger_preview()

    def on_add_name(self) -> None:
        if self._edit_lock:
            return
        iid = self.dialog.rules_tree.insert("", tk.END, values=("",))
        self.dialog.rules_tree.yview_moveto(1.0)
        self._edit_item(iid, "")

    def on_item_double_click(self, event: tk.Event) -> None:
        iid = self.dialog.rules_tree.identify_row(event.y)
        if not iid:
            return
        text = self.dialog.rules_tree.item(iid, "values")[0]
        self._edit_item(iid, text)

    def _edit_item(self, iid: str, initial_text: str = "") -> None:
        if self._rule_entry is not None:
            self._rule_entry.destroy()

        tree = self.dialog.rules_tree
        tree.selection_remove(*tree.selection())

        tree.update_idletasks()
        item_bbox = tree.bbox(iid, column="name")
        row_height = Style().lookup('Treeview', 'rowheight')
        content_w = tree.winfo_width() - tree.winfo_children()[0].winfo_width()

        if item_bbox:
            ix, iy, _, ih = item_bbox
            entry_x, entry_y, entry_w, entry_h = ix, iy, content_w - ix, ih
        else:
            children = tree.get_children()
            row_idx = children.index(iid)
            entry_x, entry_y = TkS(1), row_idx * row_height
            entry_w, entry_h = content_w - TkS(1), row_height

        entry = tk.Entry(tree, bd=0, highlightthickness=1)
        entry.insert(0, initial_text)
        entry.select_range(0, tk.END)
        entry.icursor(tk.END)
        self._rule_entry = entry
        self._edit_lock = True

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
                self.refilter_preview()
            elif not initial_text:
                tree.delete(iid)
            self._edit_lock = False
            entry.master.after_idle(lambda e=entry: e.destroy())

        def on_cancel(event=None):
            nonlocal _confirming
            if _confirming:
                return
            _confirming = True
            if not initial_text:
                tree.delete(iid)
            self._edit_lock = False
            entry.master.after_idle(lambda e=entry: e.destroy())

        entry.place(x=entry_x, y=entry_y, width=entry_w, height=entry_h)
        entry.focus_set()
        entry.bind("<Return>", on_confirm)
        entry.bind("<FocusOut>", on_confirm)
        entry.bind("<Escape>", on_cancel)

    def trigger_preview(self) -> None:
        self._cancel_scan = True
        self.dialog.stop_btn.pack(side=tk.RIGHT, padx=(TkS(10), 0))
        self._preview_cache.clear()
        self._scan_cache.clear()
        self._preview_total = 0
        self._preview_excluded = 0

        dir_path = self.dialog.preview_path_entry.get().strip()
        if not dir_path or not Path(dir_path).is_dir():
            self.dialog.stop_btn.pack_forget()
            return

        self.dialog.preview_tree.delete(*self.dialog.preview_tree.get_children())
        self.dialog.preview_status_label.config(text=_("正在扫描目录结构...（点击停止终止扫描）"))

        rules = self.collect_rules()
        self._cancel_scan = False
        self._scan_thread = Thread(
            target=self._do_preview, args=(dir_path, rules), daemon=True
        )
        self._scan_thread.start()

    def _do_preview(self, target_dir: str, rules: list[str]) -> None:
        pre_rules = exclude_rules.compile_rules([])
        excl_rules = exclude_rules.compile_rules(rules)

        scan_cache: list[tuple[str, bool]] = []
        total = 0

        def _walk(path: str) -> None:
            nonlocal total
            try:
                with os.scandir(path) as it:
                    for entry in it:
                        if self._cancel_scan:
                            return

                        rel = os.path.relpath(entry.path, target_dir).replace("\\", "/")
                        total += 1

                        if entry.is_dir(follow_symlinks=False):
                            scan_cache.append((rel, True))
                            _walk(entry.path)

                        elif entry.is_file(follow_symlinks=False):
                            if pre_rules and pre_rules.should_skip_file(entry, target_dir):
                                continue
                            scan_cache.append((rel, False))

                        if total % PROGRESS_INTERVAL == 0:
                            try:
                                self.dialog.after(
                                    0, lambda t=total: self._update_status(t, 0)
                                )
                            except Exception:
                                pass
            except PermissionError:
                pass

        _walk(target_dir)

        excluded_cache, excluded_count, truncated = self._compute_excluded(
            scan_cache, excl_rules, target_dir
        ) if excl_rules else ([], 0, False)

        try:
            self.dialog.after(0, lambda: self._preview_complete(
                excluded_cache, scan_cache, total, excluded_count, truncated
            ))
        except Exception:
            pass

    def _update_status(self, total: int, excluded: int) -> None:
        if self._closed:
            return
        self.dialog.preview_status_label.config(text=_("已排除 {excluded} 项（共扫描 {total} 项）", excluded=excluded, total=total))

    def _preview_complete(self, cache, scan_cache, total, excluded, truncated) -> None:
        if self._closed:
            return
        self._preview_cache = cache
        self._scan_cache = scan_cache
        self._preview_total = total
        self._preview_excluded = excluded
        self._preview_truncated = truncated

        self.dialog.stop_btn.pack_forget()

        self._refresh_preview_tree()

    @staticmethod
    def _filter_topmost(dirs: list[str], files: list[str]) -> tuple[list[str], list[str]]:
        kept_dirs = []
        prefixes = set()
        for d in dirs:
            if not any(d.startswith(p + "/") for p in prefixes):
                kept_dirs.append(d)
                prefixes.add(d)
        kept_files = [f for f in files if not any(f.startswith(p + "/") for p in prefixes)]
        return kept_dirs, kept_files

    def _refresh_preview_tree(self) -> None:
        selected = self.dialog.rules_tree.selection()
        filtered = self._preview_cache

        if selected:
            rule_text = self.dialog.rules_tree.item(selected[0], "values")[0].strip()
            if rule_text.startswith("!"):
                self.dialog.preview_tree.delete(*self.dialog.preview_tree.get_children())
                self.dialog.preview_status_label.config(text=_("取反规则本身不排除文件"))
                return
            if exclude_rules.ExcludeRules.SPECIAL_RULE_PATTERN.match(rule_text):
                target_dir = self.dialog.preview_path_entry.get().strip()
                if target_dir and self._scan_cache:
                    single_excl = exclude_rules.compile_rules([rule_text])
                    if single_excl:
                        filtered = self._compute_excluded(self._scan_cache, single_excl, target_dir)[0]
                    else:
                        filtered = []
                else:
                    filtered = []
            else:
                try:
                    single_spec = PathSpec.from_lines(GitWildMatchPattern, [rule_text.lower()])
                    filtered = [
                        (rel, is_dir) for rel, is_dir in self._preview_cache
                        if single_spec.match_file(rel.lower() + ("/" if is_dir else ""))
                    ]
                except Exception:
                    filtered = self._preview_cache

        self.dialog.preview_tree.delete(*self.dialog.preview_tree.get_children())
        dirs = sorted(rel for rel, is_dir in filtered if is_dir)
        files = sorted(rel for rel, is_dir in filtered if not is_dir)
        dirs, files = self._filter_topmost(dirs, files)

        for rel in dirs:
            self.dialog.preview_tree.insert("", tk.END, values=("\U0001f4c2" + rel,))
        for rel in files:
            self.dialog.preview_tree.insert("", tk.END, values=("\U0001f4c4" + rel,))

        dir_count = len(dirs)
        file_count = len(files)
        self.dialog.preview_status_label.configure(foreground="")
        if self._preview_truncated:
            self.dialog.preview_status_label.config(text=_("排除项过多，仅展示前 {max} 条，建议缩小预览范围", max=MAX_PREVIEW_ITEMS))
        elif dir_count == 0 and file_count == 0:
            self.dialog.preview_status_label.configure(foreground="red")
            self.dialog.preview_status_label.config(text=_("显示排除：0 个目录，0 个文件 — 当前规则无匹配项"))
        else:
            self.dialog.preview_status_label.config(text=_("显示排除：{dirs} 个目录，{files} 个文件", dirs=dir_count, files=file_count))

    def refilter_preview(self) -> None:
        if not self._scan_cache:
            return
        target_dir = self.dialog.preview_path_entry.get().strip()
        if not target_dir:
            return

        rules = self.collect_rules()
        rules_obj = exclude_rules.compile_rules(rules)
        if not rules_obj:
            self._preview_cache.clear()
            self._preview_excluded = 0
            self._refresh_preview_tree()
            return

        excluded_cache, excluded_count, truncated = self._compute_excluded(
            self._scan_cache, rules_obj, target_dir
        )

        self._preview_cache = excluded_cache
        self._preview_excluded = excluded_count
        self._preview_total = len(self._scan_cache)
        self._preview_truncated = truncated

        self.dialog.stop_btn.pack_forget()
        self._refresh_preview_tree()

    def load_rules_into_view(self) -> None:
        rules = self.setting.model.index.exclude_rules or []
        for rule in rules:
            self.dialog.rules_tree.insert("", tk.END, values=(rule,))
        self.dialog.preview_status_label.config(text=_("被排除索引的文件夹/文件"))

    @staticmethod
    def open_help_doc() -> None:
        doc_path = Path(__file__).parent.parent / "docs" / "exclude_rules.html"
        file_ops.open_file(doc_path)

    def on_preview_double_click(self, event: tk.Event) -> None:
        item = self.dialog.preview_tree.identify_row(event.y)
        if not item:
            return
        raw = self.dialog.preview_tree.item(item, "values")[0].strip()
        path = raw[1:] if len(raw) > 1 else raw
        preview_dir = self.dialog.preview_path_entry.get().strip()
        if preview_dir and path:
            full_path = os.path.join(preview_dir, path)
            if Path(full_path).exists():
                file_ops.open_file(full_path)

    def on_save(self) -> None:
        self._closed = True
        self._cancel_scan = True

        try:
            self.setting.model.index.exclude_rules = self.collect_rules()
            self.setting.save()
            self.dialog.destroy()
        except Exception as e:
            logging.error("on_save error: %s", e, exc_info=True)
            try:
                self.dialog.destroy()
            except Exception:
                pass
