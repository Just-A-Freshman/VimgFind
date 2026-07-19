from __future__ import annotations

from pathlib import Path
from tkinter import messagebox, filedialog
from typing import TYPE_CHECKING
import logging
import tkinter as tk

from tqdm import tqdm
from views import ExcludeDialog

from .exclude_controller import ExcludePreviewController
from utils.i18n import _
import utils.decorators as decorators
import utils.idle_tracker as idle_tracker

if TYPE_CHECKING:
    from .app_controller import AppController


class IndexController:
    def __init__(self, app_controller: AppController) -> None:
        self.app = app_controller
        self._is_updating: bool = False
        self._is_auto_updating: bool = False

    @property
    def is_updating(self) -> bool:
        return self._is_updating

    @property
    def is_auto_updating(self) -> bool:
        return self._is_auto_updating

    def update_index_tip(self) -> None:
        assert self.app.search_tools
        valid_index_count = self.app.search_tools.valid_index_count
        invalid_index_count = self.app.search_tools.total_index_count - self.app.search_tools.valid_index_count
        invalid_index_ratio = invalid_index_count / max(self.app.search_tools.total_index_count, 1)
        self.app.view.index_tab.index_tip_label.config(text=_("当前索引图库({count}张图片)", count=valid_index_count))
        self.app.view.index_tab.index_tooltip.text = _(
            "总占用槽位：{total}\n无效索引数：{invalid}\n占比：{ratio:.2f}%",
            total=self.app.search_tools.total_index_count,
            invalid=invalid_index_count,
            ratio=invalid_index_ratio * 100,
        )

    def switch_model(self, event) -> None:
        idx = event.widget.current()
        if idx < 0:
            return
        models = self.app.model_controller.get_downloaded_models()
        if idx < len(models):
            self.app.model_controller.switch_model(models[idx].meta.id)

    def add_search_dir(self, dir_path: str = "") -> None:
        if dir_path != "" and not Path(dir_path).is_dir():
            return
        if dir_path == "":
            dir_path = filedialog.askdirectory(title=_("选择索引文件夹"))
            if not dir_path:
                return
        search_dirs: list = self.app.setting.model.index.search_dir
        if dir_path in search_dirs:
            messagebox.showinfo(_("提示"), _("新索引的目录已包含在当前索引目录中！"))
            return
        for search_dir in search_dirs:
            if Path(dir_path).is_relative_to(search_dir):
                messagebox.showinfo(_("提示"), _("该文件夹是索引目录的子文件夹！"))
                return
        search_dirs.append(dir_path)
        self.refresh_index_dataset_table()
        self.app.setting.save()

    @decorators.send_task
    @decorators.redirect_output
    def rebuild_index(self) -> None:
        def rebuild_current_model() -> None:
            assert self.app.search_tools
            progress_bar = tqdm(total=0, ascii=False, ncols=50)
            self.app.search_tools.rebuild_index(
                [d for d in self.app.setting.model.index.search_dir if Path(d).exists()],
                int(float(self.app.view.index_tab.update_threads_count_scale.get())),
                self.app.setting.model.index.exclude_rules or [], 
                progress_bar
            )

        answer = messagebox.askyesno(_("提示"), _("重建索引极其耗时，\n您确定要进行重建吗？"))
        if not answer:
            return
        if self.app.setting.app.update_index_range == "all" and len(self.app.model_controller.get_downloaded_models()) > 1:
            answer = messagebox.askyesno(_("提示"), _("您确定要重建全部模型的索引吗？"))
            if not answer:
                return
        self._is_auto_updating = False
        self._run_index_task(rebuild_current_model)

    @decorators.send_task
    @decorators.redirect_output
    def sync_index(self, show_message: bool = True, auto: bool = False) -> None:
        def sync_current_model() -> None:
            assert self.app.search_tools
            self.app.search_tools.remove_nonexists()
            progress_bar = tqdm(total=0, ascii=False, ncols=50)
            self.app.search_tools.update_index(
                [d for d in self.app.setting.model.index.search_dir if Path(d).exists()],
                int(float(self.app.view.index_tab.update_threads_count_scale.get())),
                self.app.setting.model.index.exclude_rules or [],
                progress_bar
            )
            self.app.search_tools.remove_duplicate()

        if auto:
            if self._is_updating:
                return
            show_message = False
            self._is_auto_updating = True
        else:
            self._is_auto_updating = False        
        self._run_index_task(sync_current_model, show_message)

    def _run_index_task(self, model_work, show_message: bool = True) -> None:
        tab = self.app.view.index_tab
        tab.delete_index_button.config(state=tk.DISABLED)
        tab.rebuild_index_button.config(state=tk.DISABLED)
        tab.update_index_button.config(
            text=_("终止索引更新"),
            command=lambda: setattr(self.app.search_tools, "force_stop_update", True)
        )
        self._is_updating = True
        self.app.model_controller.on_model_select()
        self.__check_queue()
        try:
            assert self.app.search_tools
            tab = self.app.view.index_tab
            tab.switch_model_combobox.config(state=tk.DISABLED)
            model_work()
            if self.app.setting.app.update_index_range == "all":
                original_id = self.app.setting.app.current_model
                remaining_models = [
                    cfg for cfg in self.app.model_controller.get_downloaded_models()
                    if cfg.meta.id != original_id
                ]
                for model in remaining_models:
                    if self.app.search_tools.force_stop_update:
                        break
                    self.app.model_controller.switch_model(model.meta.id, resend_search=False)
                    model_work()
                self.app.model_controller.switch_model(original_id)
            if show_message:
                messagebox.showinfo(_("提示"), _("索引更新完成！"))
        except Exception as e:
            messagebox.showerror(_("错误"), _("索引更新时遇到错误：{e}", e=str(e)))
        finally:
            tab.switch_model_combobox.config(state="readonly")
            self.app.view.switch_tab.tab(self.app.view.search_tab, state=tk.NORMAL)
            setattr(self.app.search_tools, "force_stop_update", False)
            self.app.view.after(1000, self.update_index_tip)
            tab.update_index_button.config(text=_("更新索引目录"), command=self.sync_index)
            tab.delete_index_button.config(state=tk.NORMAL)
            tab.rebuild_index_button.config(state=tk.NORMAL)
            self.app.model_controller.on_model_select()
            self._is_updating = False
            self._is_auto_updating = False

    def refresh_index_dataset_table(self) -> None:
        tb = self.app.view.index_tab.index_dataset_table
        for item in tb.get_children():
            tb.delete(item)
        search_dirs = self.app.setting.model.index.search_dir
        for index, dir_path in enumerate(search_dirs, 1):
            tb.insert("", tk.END, values=(index, dir_path))
        self.app.filter_controller.refresh_folder_filter()

    def open_exclude_dialog(self) -> None:
        dialog = ExcludeDialog(self.app.view, self.app.setting)
        controller = ExcludePreviewController(dialog, self.app.setting)
        dialog.help_btn.config(command=controller.open_help_doc)
        dialog.stop_btn.config(command=controller.stop_scan)
        dialog.add_rule_btn.config(command=controller.on_add_name)
        dialog.del_rule_btn.config(command=controller.on_delete_selected)
        dialog.browse_btn.config(command=controller.on_browse)
        dialog.preview_path_entry.bind("<Return>", lambda e: controller.trigger_preview())
        dialog.rules_tree.bind("<<TreeviewSelect>>", controller.on_rule_select)
        dialog.rules_tree.bind("<Double-Button-1>", controller.on_item_double_click)
        dialog.preview_tree.bind("<Double-Button-1>", controller.on_preview_double_click)
        dialog.protocol("WM_DELETE_WINDOW", controller.on_save)
        controller.load_rules_into_view()

    def on_reorder(self, source_idx: int, target_idx: int) -> None:
        search_dirs: list = self.app.setting.model.index.search_dir
        dir_to_move = search_dirs.pop(source_idx)
        search_dirs.insert(target_idx, dir_to_move)
        self.app.filter_controller.refresh_folder_filter()

    @decorators.send_task
    @decorators.redirect_output
    def delete_search_dir(self) -> None:
        assert self.app.search_tools
        selected = self.app.view.index_tab.index_dataset_table.selection()
        if not selected:
            return
        answer = messagebox.askyesno(_("提示"), _("你确定要删除选中目录吗？"))
        if not answer:
            return
        self._is_updating = True
        self.__check_queue()
        dirs_to_delete = []
        search_dir: list = self.app.setting.model.index.search_dir
        for item in selected:
            delete_search_dir = self.app.view.index_tab.index_dataset_table.item(item, 'values')[1]
            dirs_to_delete.append(delete_search_dir)
            search_dir.remove(delete_search_dir)
            self.app.view.index_tab.index_dataset_table.delete(item)
        self.refresh_index_dataset_table()
        remaining_dirs = [d for d in self.app.setting.model.index.search_dir]
        for dir_path in dirs_to_delete:
            self.app.search_tools.remove_files_in_directory(dir_path, remaining_dirs)
        self.app.search_tools.remove_nonexists()
        self.app.setting.save()
        self._is_updating = False
        self.app.view.after(1000, self.update_index_tip)

    def toggle_auto_update(self) -> None:
        enabled = self.app.view.index_tab.auto_update_checkbutton.instate(['selected'])
        self.app.setting.app.auto_update_index = enabled
        if enabled:
            if not hasattr(self, 'idle_tracker'):
                self.idle_tracker = idle_tracker.IdleMonitor(
                    root=self.app.view,
                    threshold=self.app.setting.app.auto_update_idle_threshold,
                    on_idle=lambda: self.sync_index(auto=True),
                )
                self.idle_tracker.start()
        else:
            if hasattr(self, 'idle_tracker'):
                self.idle_tracker.stop()
                del self.idle_tracker
            if self.is_auto_updating and self.app.search_tools:
                self.app.search_tools.force_stop_update = True

    @decorators.send_task
    def clean_excluded(self) -> None:
        assert self.app.search_tools
        search_dirs = self.app.setting.model.index.search_dir
        rules = self.app.setting.model.index.exclude_rules or []
        if not rules:
            messagebox.showinfo(_("提示"), _("当前没有设置排除规则。"))
            return
        if not search_dirs:
            messagebox.showinfo(_("提示"), _("当前没有索引目录。"))
            return

        excluded = self.app.search_tools.get_excluded_files(rules, search_dirs)
        if not excluded:
            messagebox.showinfo(_("提示"), _("索引中没有匹配排除规则的文件。"))
            return

        answer = messagebox.askyesno(
            _("确认清理"),
            _("将在索引中移除 {count} 个匹配排除规则的文件记录。\n\n此操作不可撤消，是否继续？", count=len(excluded))
        )
        if not answer:
            return
        self.app.search_tools.remove_files(excluded)
        self.app.search_tools.remove_nonexists()
        self.app.view.after(1000, self.update_index_tip)
        messagebox.showinfo(_("提示"), _("已清理 {count} 个文件记录。", count=len(excluded)))

    def __check_queue(self) -> None:
        try:
            while True:
                message = decorators.progress_queue.get_nowait()
                self.app.view.index_tab.index_tip_label.config(text=message)
        except Exception as e:
            logging.warning(f"__check_queue 异常: {e}")
        if self._is_updating:
            self.app.view.after(200, self.__check_queue)
