from __future__ import annotations

from pathlib import Path
from tkinter import filedialog, font
import tkinter as tk
import logging
import os

from pathspec.patterns.gitwildmatch import GitWildMatchPattern
from pathspec import PathSpec
from ttkbootstrap import Style

from config.settings import Setting, TkS
from utils.i18n import _
from views.exclude_dialog import ExcludeDialog
import utils.exclude_rules as exclude_rules
import utils.file_ops as file_ops
import utils.decorators as decorators


MAX_PREVIEW_ITEMS = 100000
PROGRESS_INTERVAL = 500


class ExcludePreviewController:
    def __init__(self, dialog: ExcludeDialog, setting: Setting) -> None:
        self.dialog = dialog
        self.setting = setting
        self.__cancel_scan = False
        self.__preview_cache: list[tuple[str, bool]] = []
        self.__scan_cache: list[tuple[str, bool]] = []
        self.__debounce_timer: str | None = None
        self.__rule_entry = None
        self.__closed = False
        self.__preview_truncated = False
        self.__edit_lock = False

    def collect_rules(self) -> list[str]:
        rules: list[str] = []
        for child in self.dialog.rules_tree.get_children():
            text = self.dialog.rules_tree.item(child, "values")[0].strip()
            if text:
                rules.append(text)
        return rules

    def on_rule_select(self, event=None) -> None:
        if len(self.__preview_cache) == 0:
            return
        if self.__debounce_timer is not None:
            self.dialog.after_cancel(self.__debounce_timer)
        self.__debounce_timer = self.dialog.after(500, self.__refresh_preview_tree)

    def on_delete_selected(self) -> None:
        selected = self.dialog.rules_tree.selection()
        if selected:
            self.dialog.rules_tree.delete(*selected)
            self.refilter_preview()

    def on_browse(self) -> None:
        dir_path = filedialog.askdirectory(parent=self.dialog.winfo_toplevel(), title=_("选择要预览的目录"))
        if dir_path:
            self.dialog.preview_path_entry.delete(0, tk.END)
            self.dialog.preview_path_entry.insert(tk.END, dir_path)
            self.trigger_preview()

    def on_add_name(self) -> None:
        if self.__edit_lock:
            return
        iid = self.dialog.rules_tree.insert("", tk.END, values=("",))
        self.dialog.rules_tree.yview_moveto(1.0)
        self.__edit_item(iid, "")

    def on_item_double_click(self, event: tk.Event) -> None:
        iid = self.dialog.rules_tree.identify_row(event.y)
        if not iid:
            return
        text = self.dialog.rules_tree.item(iid, "values")[0]
        self.__edit_item(iid, text)

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
        self.__closed = True
        self.__cancel_scan = True

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

    def refilter_preview(self) -> None:
        if not self.__scan_cache:
            return
        target_dir = self.dialog.preview_path_entry.get().strip()
        if not target_dir:
            return

        rules = self.collect_rules()
        rules_obj = exclude_rules.compile_rules(rules)
        if not rules_obj:
            self.__preview_cache.clear()
            self.__refresh_preview_tree()
            return

        excluded_cache, truncated = self.__compute_excluded(
            self.__scan_cache, rules_obj, target_dir
        )

        self.__preview_cache = excluded_cache
        self.__preview_truncated = truncated

        self.dialog.stop_btn.pack_forget()
        self.__refresh_preview_tree()

    def load_rules_into_view(self) -> None:
        rules = self.setting.model.index.exclude_rules or []
        for rule in rules:
            self.dialog.rules_tree.insert("", tk.END, values=(rule,))
        self.dialog.preview_status_label.config(text=_("被排除索引的文件夹/文件"))

    def trigger_preview(self) -> None:
        self.__cancel_scan = True
        self.dialog.stop_btn.pack(side=tk.RIGHT, padx=(TkS(10), 0))
        self.__preview_cache.clear()
        self.__scan_cache.clear()

        dir_path = self.dialog.preview_path_entry.get().strip()
        if not dir_path or not Path(dir_path).is_dir():
            self.dialog.stop_btn.pack_forget()
            return

        self.dialog.preview_tree.delete(*self.dialog.preview_tree.get_children())
        self.dialog.preview_status_label.config(text=_("正在扫描目录结构...（点击停止终止扫描）"))

        rules = self.collect_rules()
        self.__cancel_scan = False
        self.__do_preview(dir_path, rules)

    def stop_scan(self) -> None:
        self.__cancel_scan = True

    def __compute_excluded(
        self,
        scan_cache: list[tuple[str, bool]],
        excl_rules,
        target_dir: str,
        max_items: int = MAX_PREVIEW_ITEMS,
    ) -> tuple[list[tuple[str, bool]], bool]:
        excluded: list[tuple[str, bool]] = []
        truncated = False
        for rel, is_dir in scan_cache:
            if len(excluded) >= max_items:
                truncated = True
                break
            full_path = os.path.join(target_dir, rel)
            if is_dir:
                if excl_rules.should_skip_dir(full_path, target_dir):
                    excluded.append((rel, True))
            elif excl_rules.should_skip_file(full_path, target_dir):
                excluded.append((rel, False))
        return excluded, truncated

    def __edit_item(self, iid: str, initial_text: str = "") -> None:
        if self.__rule_entry is not None:
            self.__rule_entry.destroy()

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
        self.__rule_entry = entry
        self.__edit_lock = True

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
            self.__edit_lock = False
            entry.master.after_idle(lambda e=entry: e.destroy())

        def on_cancel(event=None):
            nonlocal _confirming
            if _confirming:
                return
            _confirming = True
            if not initial_text:
                tree.delete(iid)
            self.__edit_lock = False
            entry.master.after_idle(lambda e=entry: e.destroy())

        entry.place(x=entry_x, y=entry_y, width=entry_w, height=entry_h)
        entry.focus_set()
        entry.bind("<Return>", on_confirm)
        entry.bind("<FocusOut>", on_confirm)
        entry.bind("<Escape>", on_cancel)

    @decorators.send_task
    def __do_preview(self, target_dir: str, rules: list[str]) -> None:
        pre_rules = exclude_rules.compile_rules([])
        excl_rules = exclude_rules.compile_rules(rules)

        scan_cache: list[tuple[str, bool]] = []
        total = 0

        def _walk(path: str) -> None:
            nonlocal total
            try:
                with os.scandir(path) as it:
                    for entry in it:
                        if self.__cancel_scan:
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
                                self.dialog.after(0, lambda t=total: (
                                    None if self.__closed else self.dialog.preview_status_label.config(
                                        text=_("已排除 {excluded} 项（共扫描 {total} 项）", excluded=0, total=t)
                                    )
                                ))
                            except Exception:
                                pass
            except PermissionError:
                pass

        _walk(target_dir)

        excluded_cache, truncated = self.__compute_excluded(
            scan_cache, excl_rules, target_dir
        ) if excl_rules else ([], False)

        try:
            self.dialog.after(0, lambda: self.__preview_complete(excluded_cache, scan_cache, truncated))
        except Exception:
            pass

    def __preview_complete(self, cache, scan_cache, truncated) -> None:
        if self.__closed:
            return
        self.__preview_cache = cache
        self.__scan_cache = scan_cache
        self.__preview_truncated = truncated
        self.dialog.stop_btn.pack_forget()

        self.__refresh_preview_tree()

    @staticmethod
    def __filter_topmost(dirs: list[str], files: list[str]) -> tuple[list[str], list[str]]:
        kept_dirs = []
        prefixes = set()
        for d in dirs:
            if not any(d.startswith(p + "/") for p in prefixes):
                kept_dirs.append(d)
                prefixes.add(d)
        kept_files = [f for f in files if not any(f.startswith(p + "/") for p in prefixes)]
        return kept_dirs, kept_files

    def __refresh_preview_tree(self) -> None:
        selected = self.dialog.rules_tree.selection()
        filtered = self.__preview_cache

        if selected:
            rule_text = self.dialog.rules_tree.item(selected[0], "values")[0].strip()
            if rule_text.startswith("!"):
                self.dialog.preview_tree.delete(*self.dialog.preview_tree.get_children())
                self.dialog.preview_status_label.config(text=_("取反规则本身不排除文件"))
                return
            if exclude_rules.ExcludeRules.SPECIAL_RULE_PATTERN.match(rule_text):
                target_dir = self.dialog.preview_path_entry.get().strip()
                if target_dir and self.__scan_cache:
                    single_excl = exclude_rules.compile_rules([rule_text])
                    if single_excl:
                        filtered = self.__compute_excluded(self.__scan_cache, single_excl, target_dir)[0]
                    else:
                        filtered = []
                else:
                    filtered = []
            else:
                try:
                    single_spec = PathSpec.from_lines(GitWildMatchPattern, [rule_text.lower()])
                    filtered = [
                        (rel, is_dir) for rel, is_dir in self.__preview_cache
                        if single_spec.match_file(rel.lower() + ("/" if is_dir else ""))
                    ]
                except Exception:
                    filtered = self.__preview_cache

        self.dialog.preview_tree.delete(*self.dialog.preview_tree.get_children())
        dirs = sorted(rel for rel, is_dir in filtered if is_dir)
        files = sorted(rel for rel, is_dir in filtered if not is_dir)
        dirs, files = self.__filter_topmost(dirs, files)

        for rel in dirs:
            self.dialog.preview_tree.insert("", tk.END, values=("\U0001f4c2" + rel,))
        for rel in files:
            self.dialog.preview_tree.insert("", tk.END, values=("\U0001f4c4" + rel,))
        self.__auto_fit_treeview_columns()
        self.dialog.preview_status_label.configure(foreground="")
        if self.__preview_truncated:
            self.dialog.preview_status_label.config(text=_("排除项过多，仅展示前 {max} 条，建议缩小预览范围", max=MAX_PREVIEW_ITEMS))
        elif len(dirs) == 0 and len(files) == 0:
            self.dialog.preview_status_label.configure(foreground="red")
            self.dialog.preview_status_label.config(text=_("显示排除：0 个目录，0 个文件 — 当前规则无匹配项"))
        else:
            self.dialog.preview_status_label.config(text=_("显示排除：{dirs} 个目录，{files} 个文件", dirs=len(dirs), files=len(files)))
    
    def __auto_fit_treeview_columns(self):
        default_font = font.nametofont("TkTextFont")
        max_width = default_font.measure(self.dialog.preview_tree.heading("path", 'text'))
        for item in self.dialog.preview_tree.get_children(''):
            cell_text = self.dialog.preview_tree.set(item, "path")
            width = default_font.measure(str(cell_text))
            if width > max_width:
                max_width = width
        self.dialog.preview_tree.column("path", width=max(max_width, self.dialog.preview_tree.winfo_width()))
