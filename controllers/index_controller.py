from __future__ import annotations

from typing import TYPE_CHECKING
from tkinter import messagebox, filedialog
from pathlib import Path
import tkinter as tk

import utils.decorators as decorators

if TYPE_CHECKING:
    from .app_controller import AppController


class IndexController(object):
    def __init__(self, app_controller: AppController) -> None:
        self.app = app_controller
        self._is_updating: bool = False
        self._drag_source: str | None = None
        self._drag_active: bool = False
        self._drop_target: str | None = None
        self._insert_before: bool | None = None
        self._drag_ghost: tk.Toplevel | None = None

    def update_index_tip(self) -> None:
        assert self.app.search_tools
        tab = self.app.view.setting_tab
        tab.index_tip_label.config(
            text=f"当前索引图库({self.app.search_tools.valid_index_count}张图片)"
        )
        self._is_updating = False

    def add_search_dir(self, dir_path: str = "") -> None:
        if dir_path != "" and not Path(dir_path).is_dir():
            return
        if dir_path == "":
            dir_path = filedialog.askdirectory(title="选择索引文件夹")
            if not dir_path:
                return
        search_dirs: list = self.app.setting.get_config("index", "search_dir")
        if dir_path in search_dirs:
            messagebox.showinfo("提示", "新索引的目录已包含在当前索引目录中！")
            return
        for search_dir in search_dirs:
            if Path(dir_path).is_relative_to(search_dir):
                messagebox.showinfo("提示", "该文件夹是索引目录的子文件夹！")
                return
        search_dirs.append(dir_path)
        self.refresh_index_dataset_table()
        self.app.setting.save_settings()

    def rebuild_index(self) -> None:
        assert self.app.search_tools
        answer = messagebox.askyesno("提示", "重建索引极其耗时，\n您确定要进行重建吗？")
        if not answer:
            return
        try:
            self.app.search_tools.reset_index()
        except (FileNotFoundError, KeyError):
            pass
        self.sync_index()

    def refresh_index_dataset_table(self) -> None:
        tb = self.app.view.setting_tab.index_dataset_table
        all_items = tb.get_children()
        all_show_dir = {tb.item(node, 'values')[1] for node in all_items}
        for index_id, item in enumerate(all_items, 1):
            _, search_dir = tb.item(item, "values")
            tb.item(item, values=(index_id, search_dir))
        search_dirs = self.app.setting.get_config("index", "search_dir")
        all_items_count = len(all_items) + 1
        for search_dir in search_dirs:
            if search_dir not in all_show_dir:
                tb.insert("", tk.END, values=(all_items_count, search_dir))
                all_items_count += 1
        self.app.filter_controller.refresh_folder_filter()

    def drag_start(self, event: tk.Event) -> None:
        tb = self.app.view.setting_tab.index_dataset_table
        item = tb.identify_row(event.y)
        if not item:
            self._drag_source = None
            return
        self._drag_source = item
        self._drag_active = False
        self._drop_target = None
        self._insert_before = None
        self._drag_ghost = None

    def drag_motion(self, event: tk.Event) -> None:
        if not self._drag_source:
            return

        if not self._drag_active:
            self._drag_active = True
            self._create_drag_ghost(event)

        self._move_drag_ghost(event)

        tb = self.app.view.setting_tab.index_dataset_table
        target = tb.identify_row(event.y)

        if not target:
            children = tb.get_children()
            if children:
                last_bbox = tb.bbox(children[-1])
                if last_bbox and event.y > last_bbox[1] + last_bbox[3]:
                    self._drop_target = None
                    self._insert_before = False
                    tb.selection_set(children[-1])
                    return
            self._drop_target = None
            self._insert_before = None
            tb.selection_set(())
            return

        if target == self._drag_source:
            self._drop_target = None
            self._insert_before = None
            tb.selection_set(self._drag_source)
            return

        bbox = tb.bbox(target)
        if not bbox:
            return

        children = list(tb.get_children())
        _, y, _, height = bbox
        self._insert_before = (event.y - y) < height // 2
        self._drop_target = target

        if self._insert_before:
            tb.selection_set(target)
        else:
            next_idx = children.index(target) + 1
            if next_idx < len(children):
                tb.selection_set(children[next_idx])
            else:
                tb.selection_set(())

    def drag_end(self, event: tk.Event) -> None:
        if self._drag_ghost:
            self._drag_ghost.destroy()
            self._drag_ghost = None

        if not self._drag_active or not self._drag_source:
            self._drag_clear_state()
            return

        try:
            tb = self.app.view.setting_tab.index_dataset_table
            items = list(tb.get_children())
            source_idx = items.index(self._drag_source)

            if self._drop_target is None and self._insert_before is False:
                target_idx = len(items)
            elif self._drop_target:
                target_idx = items.index(self._drop_target)
                if not self._insert_before:
                    target_idx += 1
            else:
                return

            if target_idx == source_idx:
                return

            search_dirs: list = self.app.setting.get_config("index", "search_dir")
            dir_to_move = search_dirs.pop(source_idx)
            search_dirs.insert(target_idx, dir_to_move)

            tb.move(self._drag_source, "", target_idx)
            for i, item in enumerate(tb.get_children(), 1):
                _, dir_path = tb.item(item, "values")
                tb.item(item, values=(i, dir_path))

            tb.selection_set(self._drag_source)
            self.app.filter_controller.refresh_folder_filter()
        finally:
            self._drag_clear_state()

    def _create_drag_ghost(self, event: tk.Event) -> None:
        source = self._drag_source
        if source is None:
            return
        tb = self.app.view.setting_tab.index_dataset_table
        values = tb.item(source, "values")
        dir_path = values[1] if len(values) > 1 else ""

        ghost = tk.Toplevel(tb)
        ghost.overrideredirect(True)
        ghost.attributes("-alpha", 0.75, "-topmost", True)

        label = tk.Label(ghost, text=str(dir_path), anchor=tk.W, padx=12, pady=6)
        label.pack()

        ghost.update_idletasks()
        ghost.geometry(f"+{event.x_root + 20}+{event.y_root - 10}")
        self._drag_ghost = ghost

    def _move_drag_ghost(self, event: tk.Event) -> None:
        if self._drag_ghost:
            self._drag_ghost.geometry(f"+{event.x_root + 20}+{event.y_root - 10}")

    def _drag_clear_state(self) -> None:
        self._drag_source = None
        self._drag_active = False
        self._drop_target = None
        self._insert_before = None
        self._drag_ghost = None

    @decorators.send_task
    @decorators.redirect_output
    def sync_index(self, show_message: bool = True) -> None:
        assert self.app.search_tools
        tab = self.app.view.setting_tab
        tab.delete_index_button.config(state=tk.DISABLED)
        tab.rebuild_index_button.config(state=tk.DISABLED)
        tab.update_index_button.config(
            text="终止索引更新",
            command=lambda: self.app.search_tools.set_force_end_update(True)   #type:ignore
        )
        self._is_updating = True
        self.__check_queue()
        self.app.search_tools.remove_nonexists()

        exclude_rules: list[str] = self.app.setting.get_config("index", "exclude_rules") or []

        for image_dir in self.app.setting.get_config("index", "search_dir"):
            if Path(image_dir).exists():
                self.app.search_tools.update_index(
                    image_dir,
                    int(float(tab.update_threads_count_scale.get())),
                    exclude_rules
                )
        self.app.search_tools.remove_duplicate()
        tab.update_index_button.config(text="更新索引目录", command=self.sync_index)
        tab.delete_index_button.config(state=tk.NORMAL)
        tab.rebuild_index_button.config(state=tk.NORMAL)
        if show_message:
            messagebox.showinfo("提示", "索引更新完成！")
        self.app.view.after(1000, self.update_index_tip)
        self.app.search_tools.set_force_end_update(False)
        self._is_updating = False

    @decorators.send_task
    @decorators.redirect_output
    def delete_search_dir(self) -> None:
        assert self.app.search_tools
        selected = self.app.view.setting_tab.index_dataset_table.selection()
        if not selected:
            return
        answer = messagebox.askyesno("提示", "你确定要删除选中目录吗？")
        if not answer:
            return
        self._is_updating = True
        self.__check_queue()
        dirs_to_delete = []
        search_dir: list = self.app.setting.get_config("index", "search_dir")
        for item in selected:
            delete_search_dir = self.app.view.setting_tab.index_dataset_table.item(item, 'values')[1]
            dirs_to_delete.append(delete_search_dir)
            search_dir.remove(delete_search_dir)
            self.app.view.setting_tab.index_dataset_table.delete(item)
        self.refresh_index_dataset_table()
        remaining_dirs = [d for d in self.app.setting.get_config("index", "search_dir")]
        for dir_path in dirs_to_delete:
            self.app.search_tools.remove_files_in_directory(dir_path, remaining_dirs)
        self.app.search_tools.remove_nonexists()
        self.app.setting.save_settings()
        self.app.view.after(1000, self.update_index_tip)

    @decorators.send_task
    def clean_excluded(self) -> None:
        assert self.app.search_tools
        search_dirs = self.app.setting.get_config("index", "search_dir")
        rules = self.app.setting.get_config("index", "exclude_rules") or []
        if not rules:
            messagebox.showinfo("提示", "当前没有设置排除规则。")
            return
        if not search_dirs:
            messagebox.showinfo("提示", "当前没有索引目录。")
            return

        excluded = self.app.search_tools.get_excluded_files(rules, search_dirs)
        if not excluded:
            messagebox.showinfo("提示", "索引中没有匹配排除规则的文件。")
            return

        answer = messagebox.askyesno(
            "确认清理",
            f"将在索引中移除 {len(excluded)} 个匹配排除规则的文件记录。\n\n"
            f"此操作不可撤消，是否继续？"
        )
        if not answer:
            return
        self.app.search_tools.remove_files(excluded)
        self.app.search_tools.remove_nonexists()
        self.app.view.after(1000, self.update_index_tip)
        messagebox.showinfo("提示", f"已清理 {len(excluded)} 个文件记录。")

    def __check_queue(self) -> None:
        try:
            while True:
                message = decorators.progress_queue.get_nowait()
                self.app.view.setting_tab.index_tip_label.config(text=message)
        except Exception:
            pass
        if self._is_updating:
            self.app.view.after(200, self.__check_queue)
