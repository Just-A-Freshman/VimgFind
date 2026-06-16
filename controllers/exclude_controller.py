"""Controller for ExcludeDialog preview scanning, filtering, and save logic."""

import os
from threading import Thread
from pathlib import Path

import pathspec
from pathspec.patterns.gitwildmatch import GitWildMatchPattern

from utils.exclude_rules import compile_rules, is_accepted_extension


MAX_PREVIEW_ITEMS = 500000
PROGRESS_INTERVAL = 500


class ExcludePreviewController:
    """Handles preview scanning, rule filtering, and save logic for ExcludeDialog."""

    def __init__(self, dialog, setting) -> None:
        self.dialog = dialog
        self.setting = setting

        self._original_rules: list[str] = (
            self.setting.get_config("index", "exclude_rules") or []
        )

        self._cancel_scan = False
        self._scan_thread: Thread | None = None
        self._hint_timer: str | None = None
        self._preview_cache: list[tuple[str, bool]] = []
        self._preview_total = 0
        self._preview_excluded = 0
        self._debounce_timer: str | None = None
        self._closed = False  # set True on save to suppress stale after() callbacks

    # ── Rule change detection ─────────────────────────────────────────

    def rules_changed(self) -> bool:
        current = self.dialog.collect_rules()
        return current != self._original_rules

    # ── Rule selection (debounced) ────────────────────────────────────

    def on_rule_select(self, event=None) -> None:
        if self._debounce_timer:
            self.dialog.after_cancel(self._debounce_timer)
        self._debounce_timer = self.dialog.after(500, self._refresh_preview_from_cache)

    # ── Preview scanning ──────────────────────────────────────────────

    def stop_scan(self) -> None:
        self._cancel_scan = True

    def trigger_preview(self) -> None:
        self._cancel_scan = True
        self.dialog.show_stop_button()
        self._preview_cache.clear()
        self._preview_total = 0
        self._preview_excluded = 0

        dir_path = self.dialog.preview_path_var.get().strip()
        if not dir_path or not Path(dir_path).is_dir():
            self.dialog.hide_stop_button()
            return

        self.dialog.clear_preview_tree()
        self.dialog.set_status("正在扫描目录结构...（点击停止终止扫描）")

        rules = self.dialog.collect_rules()
        if not rules:
            self.dialog.set_status("被排除索引的文件夹/文件")
            self.dialog.hide_stop_button()
            return

        self._cancel_scan = False
        self._scan_thread = Thread(
            target=self._do_preview, args=(dir_path, rules), daemon=True
        )
        self._scan_thread.start()

    def _do_preview(self, target_dir: str, rules: list[str]) -> None:
        rules_obj = compile_rules(rules)
        if not rules_obj:
            self.dialog.after(0, self._preview_empty)
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
                            else:
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
                            self.dialog.after(
                                0, lambda t=total, e=excluded: self._update_status(t, e)
                            )
            except PermissionError:
                pass

        _walk(target_dir)

        self.dialog.after(
            0, lambda: self._preview_complete(cache, total, excluded, truncated)
        )

    def _update_status(self, total: int, excluded: int) -> None:
        if self._closed:
            return
        self.dialog.set_status(f"已排除 {excluded} 项（共扫描 {total} 项）")

    def _preview_empty(self) -> None:
        if self._closed:
            return
        self.dialog.hide_stop_button()
        self.dialog.set_status("被排除索引的文件夹/文件")

    def _preview_complete(self, cache, total, excluded, truncated) -> None:
        if self._closed:
            return
        self._preview_cache = cache
        self._preview_total = total
        self._preview_excluded = excluded

        self.dialog.hide_stop_button()
        self.dialog.reset_status_foreground()

        if truncated:
            self.dialog.set_status(
                f"排除项过多，仅展示前 {MAX_PREVIEW_ITEMS} 条，建议缩小预览范围"
            )
        else:
            self.dialog.set_status(f"被排除索引的文件夹/文件（共 {excluded} 项）")

        if excluded > 0 and excluded >= total and not truncated:
            self.dialog.set_status("⚠️ 当前规则排除了所有文件，索引结果为空")
            self.dialog.set_status_foreground("red")

        self._refresh_preview_tree()

    def _refresh_preview_from_cache(self) -> None:
        if self._closed or not self._preview_cache:
            return
        self._refresh_preview_tree()

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
        for rel in dirs:
            self.dialog.preview_tree.insert("", "end", values=("\U0001f4c2" + rel,))
        for rel in files:
            self.dialog.preview_tree.insert("", "end", values=("\U0001f4c4" + rel,))

        if not selected and self._preview_excluded >= self._preview_total > 0:
            self.dialog.set_status_foreground("red")
            self.dialog.set_status("⚠️ 当前规则排除了所有文件，索引结果为空")

    # ── Save ──────────────────────────────────────────────────────────

    def on_save(self) -> None:
        self._closed = True
        self._cancel_scan = True
        rules = self.dialog.collect_rules()
        self.setting.modity_config("index", "exclude_rules", rules)
        self.setting.save_settings()
        self.dialog.save_result = True

        if self.rules_changed():
            if self._hint_timer:
                self.dialog.after_cancel(self._hint_timer)
            self.dialog.title("排除规则已更新，点击[设置]>[清理排除项]清理已索引文件")
            self._hint_timer = self.dialog.after(5000, self._finish_save)
        else:
            self.dialog.destroy()

    def _finish_save(self) -> None:
        self._hint_timer = None
        self.dialog.title("排除设置")
        self.dialog.destroy()
