import os
import logging
import tkinter as tk
from threading import Thread
from pathlib import Path

import pathspec
from pathspec.patterns.gitwildmatch import GitWildMatchPattern

import utils.file_ops as file_ops
import utils.exclude_rules as exclude_rules
from views.exclude_dialog import ExcludeDialog
from settings import Setting


MAX_PREVIEW_ITEMS = 100000
PROGRESS_INTERVAL = 500


class ExcludePreviewController:
    def __init__(self, dialog: ExcludeDialog, setting: Setting) -> None:
        self.dialog = dialog
        self.setting = setting

        self._original_rules: list[str] = (self.setting.get_config("index", "exclude_rules") or [])
        self._cancel_scan = False
        self._scan_thread: Thread | None = None
        self._preview_cache: list[tuple[str, bool]] = []    # excluded items (for display)
        self._scan_cache: list[tuple[str, bool]] = []       # all scanned items (for re-filter)
        self._preview_total = 0
        self._preview_excluded = 0
        self._debounce_timer: int | None = None
        self._closed = False  # set True on save to suppress stale after() callbacks
        self._preview_truncated = False

    def rules_changed(self) -> bool:
        current = self.dialog.collect_rules()
        return current != self._original_rules

    def on_rule_select(self, event=None) -> None:
        if self._debounce_timer is not None:
            self.dialog.after_cancel(self._debounce_timer)
        self._debounce_timer = self.dialog.after(500, self._refresh_preview_from_cache)

    def stop_scan(self) -> None:
        self._cancel_scan = True

    def trigger_preview(self) -> None:
        self._cancel_scan = True
        self.dialog.show_stop_button()
        self._preview_cache.clear()
        self._scan_cache.clear()
        self._preview_total = 0
        self._preview_excluded = 0

        dir_path = self.dialog.preview_path_var.get().strip()
        if not dir_path or not Path(dir_path).is_dir():
            self.dialog.hide_stop_button()
            return

        self.dialog.clear_preview_tree()
        self.dialog.set_status("正在扫描目录结构...（点击停止终止扫描）")

        rules = self.dialog.collect_rules()
        self._cancel_scan = False
        self._scan_thread = Thread(
            target=self._do_preview, args=(dir_path, rules), daemon=True
        )
        self._scan_thread.start()

    def _do_preview(self, target_dir: str, rules: list[str]) -> None:
        rules_obj = exclude_rules.compile_rules(rules)

        excluded_cache: list[tuple[str, bool]] = []
        scan_cache: list[tuple[str, bool]] = []
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
                            scan_cache.append((rel, True))
                            if rules_obj and rules_obj.is_excluded(rel, is_dir=True):
                                excluded_cache.append((rel, True))
                                excluded += 1
                                if excluded >= MAX_PREVIEW_ITEMS:
                                    truncated = True
                                    return
                            else:
                                _walk(entry.path)
                        elif entry.is_file(follow_symlinks=False):
                            if not exclude_rules.is_accepted_extension(entry.name):
                                continue
                            scan_cache.append((rel, False))
                            if rules_obj and rules_obj.is_excluded(rel, is_dir=False):
                                excluded_cache.append((rel, False))
                                excluded += 1
                                if excluded >= MAX_PREVIEW_ITEMS:
                                    truncated = True
                                    return

                        if total % PROGRESS_INTERVAL == 0:
                            try:
                                self.dialog.after(
                                    0, lambda t=total, e=excluded: self._update_status(t, e)
                                )
                            except Exception:
                                pass
            except PermissionError:
                pass

        _walk(target_dir)

        try:
            self.dialog.after(0, lambda: self._preview_complete(excluded_cache, scan_cache, total, excluded, truncated))
        except Exception:
            pass

    def _update_status(self, total: int, excluded: int) -> None:
        if self._closed:
            return
        self.dialog.set_status(f"已排除 {excluded} 项（共扫描 {total} 项）")

    def _preview_complete(self, cache, scan_cache, total, excluded, truncated) -> None:
        if self._closed:
            return
        self._preview_cache = cache
        self._scan_cache = scan_cache
        self._preview_total = total
        self._preview_excluded = excluded
        self._preview_truncated = truncated

        self.dialog.hide_stop_button()

        self._refresh_preview_tree()

    def _refresh_preview_from_cache(self) -> None:
        if self._closed or not self._preview_cache:
            return
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
                self.dialog.clear_preview_tree()
                self.dialog.set_status("取反规则本身不排除文件")
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

        self.dialog.clear_preview_tree()
        dirs = sorted(rel for rel, is_dir in filtered if is_dir)
        files = sorted(rel for rel, is_dir in filtered if not is_dir)
        dirs, files = self._filter_topmost(dirs, files)

        for rel in dirs:
            self.dialog.preview_tree.insert("", tk.END, values=("\U0001f4c2" + rel,))
        for rel in files:
            self.dialog.preview_tree.insert("", tk.END, values=("\U0001f4c4" + rel,))

        dir_count = len(dirs)
        file_count = len(files)
        self.dialog.reset_status_foreground()
        if self._preview_truncated:
            self.dialog.set_status(
                f"排除项过多，仅展示前 {MAX_PREVIEW_ITEMS} 条，建议缩小预览范围"
            )
        elif dir_count == 0 and file_count == 0:
            self.dialog.set_status_foreground("red")
            self.dialog.set_status("显示排除：0 个目录，0 个文件 — 当前规则无匹配项")
        else:
            self.dialog.set_status(f"显示排除：{dir_count} 个目录，{file_count} 个文件")

    def refilter_preview(self) -> None:
        if not self._scan_cache:
            return
        rules = self.dialog.collect_rules()
        rules_obj = exclude_rules.compile_rules(rules)
        if not rules_obj:
            self._preview_cache.clear()
            self._preview_excluded = 0
            self._refresh_preview_tree()
            return

        excluded_cache: list[tuple[str, bool]] = []
        excluded = 0
        truncated = False
        for rel, is_dir in self._scan_cache:
            if excluded >= MAX_PREVIEW_ITEMS:
                truncated = True
                break
            if rules_obj.is_excluded(rel, is_dir):
                excluded_cache.append((rel, is_dir))
                excluded += 1

        self._preview_cache = excluded_cache
        self._preview_excluded = excluded
        self._preview_total = len(self._scan_cache)
        self._preview_truncated = truncated

        self.dialog.hide_stop_button()
        self._refresh_preview_tree()

    def load_rules_into_view(self) -> None:
        rules = self.setting.get_config("index", "exclude_rules") or []
        for rule in rules:
            self.dialog.rules_tree.insert("", tk.END, values=(rule,))
        self.dialog.set_status("被排除索引的文件夹/文件")

    @staticmethod
    def open_help_doc() -> None:
        doc_path = Path(__file__).parent.parent / "docs" / "exclude_rules.md"
        file_ops.open_file(doc_path)

    def on_preview_double_click(self, event: tk.Event) -> None:
        item = self.dialog.preview_tree.identify_row(event.y)
        if not item:
            return
        raw = self.dialog.preview_tree.item(item, "values")[0].strip()
        path = raw[1:] if len(raw) > 1 else raw
        preview_dir = self.dialog.preview_path_var.get().strip()
        if preview_dir and path:
            full_path = os.path.join(preview_dir, path)
            if Path(full_path).exists():
                file_ops.open_file(full_path)

    def on_save(self) -> None:
        self._closed = True
        self._cancel_scan = True

        try:
            rules = self.dialog.collect_rules()
            self.setting.modify_config("index", "exclude_rules", rules)
            self.setting.save_settings()
            self.dialog.destroy()
        except Exception as e:
            logging.error("on_save error: %s", e, exc_info=True)
            try:
                self.dialog.destroy()
            except Exception:
                pass
