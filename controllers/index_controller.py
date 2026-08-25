from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING
from pathlib import Path
from tkinter import messagebox, filedialog
import tkinter as tk
import logging

from tqdm import tqdm

from .exclude_controller import ExcludePreviewController
from utils.i18n import _
import utils.file_ops as file_ops
import utils.unc_ops as unc_ops
import utils.decorators as decorators
import utils.idle_tracker as idle_tracker

if TYPE_CHECKING:
    from .app_controller import AppController


RANGE_LABEL = {"current": "当前模型", "all": "全部模型"}
class IndexController:
    def __init__(self, app_controller: AppController) -> None:
        self.app = app_controller
        self.__is_updating: bool = False
        self.__is_auto_updating: bool = False
        self._is_cleaning: bool = False

    def env_init(self) -> None:
        self.refresh_index_dataset_table()
        self.update_index_tip()
        tab = self.app.view.index_tab
        self.refresh_switch_model_combobox()
        tab.update_range_combobox.set(_(RANGE_LABEL[self.app.setting.app.update_index_range]))
        tab.update_threads_count_scale.set(self.app.setting.app.max_work_thread)
        if self.app.setting.app.auto_update_index:
            tab.auto_update_checkbutton.invoke()

        # bind event
        tab.index_dataset_table.config(on_reorder=self.__on_reorder)
        tab.add_index_button.config(command=self.add_search_dir)
        tab.clean_excluded_button.config(command=self.__clean_excluded)
        tab.update_index_button.config(command=self.__sync_index)
        tab.delete_index_button.config(command=self.__delete_search_dir)
        tab.rebuild_index_button.config(command=self.__rebuild_index)
        tab.auto_update_checkbutton.config(command=self.__toggle_auto_update)
        tab.exclude_button.config(command=self.__open_exclude_dialog)

        tab.index_dataset_table.bind("<Double-Button-1>", self.__open_dataset_folder)
        tab.switch_model_combobox.bind("<<ComboboxSelected>>", self.__switch_model)
        tab.switch_model_combobox.bind("<MouseWheel>", lambda _: "break")
        tab.update_range_combobox.bind(
            "<<ComboboxSelected>>", lambda e: setattr(
                self.app.setting.app, "update_index_range", 
                next(k for k, v in RANGE_LABEL.items() if _(v) == e.widget.get())
        ))
        tab.update_threads_count_scale.bind("<ButtonRelease-1>", lambda e: setattr(self.app.setting.app, "max_work_thread", int(float(e.widget.get()))))
        self.app.model_controller.add_models_updated_callback(self.refresh_switch_model_combobox)

    def refresh_switch_model_combobox(self) -> None:
        tab = self.app.view.index_tab
        downloaded_models = self.app.model_controller.get_downloaded_models()
        tab.switch_model_combobox.config(values=[i.meta.name for i in downloaded_models])
        tab.switch_model_combobox.set(next((i.meta.name for i in downloaded_models if i.meta.id == self.app.setting.app.current_model), ""))

    @property
    def is_updating(self) -> bool:
        return self.__is_updating

    @property
    def is_auto_updating(self) -> bool:
        return self.__is_auto_updating

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

    def add_search_dir(self, dir_path: str = "") -> None:
        if dir_path != "" and not Path(dir_path).is_dir():
            return
        if dir_path == "":
            dir_path = filedialog.askdirectory(title=_("选择索引文件夹"))
            if not dir_path:
                return

        if file_ops.get_path_type(dir_path) == "mapped_drive":
            unc_path = unc_ops.resolve_mapped_drive(dir_path)
            if unc_path != dir_path:
                messagebox.showinfo(_("提示"), _("已将网络映射盘「{drive}」转换为 UNC 路径「{unc}」", drive=dir_path, unc=unc_path))
                dir_path = unc_path

        search_dirs: list = self.app.setting.model.index.search_dir
        if dir_path in search_dirs:
            messagebox.showinfo(_("提示"), _("新索引的目录已包含在当前索引目录中！"))
            return
        for search_dir in search_dirs:
            if file_ops.is_path_under(dir_path, search_dir):
                messagebox.showinfo(_("提示"), _("该文件夹是索引目录的子文件夹！"))
                return
        search_dirs.append(dir_path)
        self.refresh_index_dataset_table()
        self.app.setting.save()

    def refresh_index_dataset_table(self) -> None:
        tb = self.app.view.index_tab.index_dataset_table
        for item in tb.get_children():
            tb.delete(item)
        search_dirs = self.app.setting.model.index.search_dir
        for index, dir_path in enumerate(search_dirs, 1):
            tb.insert("", tk.END, values=(index, dir_path))
        self.app.filter_controller.refresh_folder_filter()

    def __on_reorder(self, source_idx: int, target_idx: int) -> None:
        search_dirs: list = self.app.setting.model.index.search_dir
        dir_to_move = search_dirs.pop(source_idx)
        search_dirs.insert(target_idx, dir_to_move)
        tree = self.app.view.index_tab.index_dataset_table
        for idx, item in enumerate(tree.get_children(""), 1):
            self.app.view.index_tab.index_dataset_table.set(item, "#1", idx)
        self.app.filter_controller.refresh_folder_filter()

    def __switch_model(self, event) -> None:
        idx = event.widget.current()
        if idx < 0:
            return
        models = self.app.model_controller.get_downloaded_models()
        if idx < len(models):
            self.app.model_controller.switch_model(models[idx].meta.id)

    @decorators.send_task
    @decorators.redirect_output
    def __sync_index(self, show_message: bool = True, auto: bool = False) -> None:
        def sync_current_model() -> None:
            assert self.app.search_tools
            tools = self.app.search_tools
            tools.remove_nonexists()
            tools.update_index(*self.__get_index_params())
            tools.remove_duplicate()
            if auto and tools.total_index_count > 100000 and tools.valid_index_count / tools.total_index_count < 0.8:
                tools.rebuild_index(*self.__get_index_params(), force_soft_rebuild=True)

        if auto:
            if self.__is_updating:
                return
            show_message = False
            self.__is_auto_updating = True
        else:
            self.__is_auto_updating = False        
        self.__run_index_task(sync_current_model, show_message)

    @decorators.send_task
    @decorators.redirect_output
    def __rebuild_index(self) -> None:
        def rebuild_current_model() -> None:
            assert self.app.search_tools
            self.app.search_tools.rebuild_index(*self.__get_index_params())

        answer = messagebox.askyesno(_("提示"), _("重建索引极其耗时，\n您确定要进行重建吗？"))
        if not answer:
            return
        if self.app.setting.app.update_index_range == "all" and len(self.app.model_controller.get_downloaded_models()) > 1:
            answer = messagebox.askyesno(_("提示"), _("您确定要重建全部模型的索引吗？"))
            if not answer:
                return
        self.__is_auto_updating = False
        self.__run_index_task(rebuild_current_model)

    def __get_index_params(self) -> tuple[list[str], int, list[str], tqdm]:
        search_dirs = self.app.setting.model.index.search_dir
        filtered_dirs: list[str] = []
        unc_dirs: list[str] = []
        for d in search_dirs:
            dtype = file_ops.get_path_type(d)
            if dtype == "local":
                if Path(d).exists():
                    filtered_dirs.append(d)
            else:
                unc_dirs.append(d)

        if unc_dirs:
            with ThreadPoolExecutor(max_workers=min(len(unc_dirs), 8)) as ex:
                fut_to_dir = {
                    ex.submit(unc_ops.is_share_online, unc_ops.get_unc_root(d) or d): d
                    for d in unc_dirs
                }
                for fut in as_completed(fut_to_dir):
                    d = fut_to_dir[fut]
                    try:
                        if fut.result():
                            filtered_dirs.append(d)
                    except Exception:
                        pass

        return (
            filtered_dirs,
            int(float(self.app.view.index_tab.update_threads_count_scale.get())),
            self.app.setting.model.index.exclude_rules or [],
            tqdm(total=0, ascii=False, ncols=50)
        )

    def __run_index_task(self, model_work, show_message: bool = True) -> None:
        tab = self.app.view.index_tab
        tab.delete_index_button.config(state=tk.DISABLED)
        tab.rebuild_index_button.config(state=tk.DISABLED)
        tab.update_index_button.config(
            text=_("终止索引更新"),
            command=lambda: setattr(self.app.search_tools, "force_stop_update", True)
        )
        self.__is_updating = True
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
            tab.update_index_button.config(text=_("更新索引目录"), command=self.__sync_index)
            tab.delete_index_button.config(state=tk.NORMAL)
            tab.rebuild_index_button.config(state=tk.NORMAL)
            self.app.model_controller.on_model_select()
            self.__is_updating = False
            self.__is_auto_updating = False

    def __open_exclude_dialog(self) -> None:
        from views.exclude_dialog import ExcludeDialog
        dialog = ExcludeDialog(self.app.view)
        if dialog.rules_tree.bind("<<TreeviewSelect>>"):
            return
        controller = ExcludePreviewController(dialog, self.app.setting)
        dialog.help_btn.config(command=lambda: self.app.setting.link_to_docs(_("排除规则")))
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

    def __open_dataset_folder(self, event: tk.Event) -> None:
        selection = self.app.view.index_tab.index_dataset_table.selection()
        if not selection:
            return
        try:
            dir_path = self.app.view.index_tab.index_dataset_table.item(selection[0], "values")[1]
            file_ops.open_file(dir_path)
        except (IndexError, FileNotFoundError) as e:
            logging.warning(f"打开目录失败: {str(e)}")

    @decorators.send_task
    @decorators.redirect_output
    def __delete_search_dir(self) -> None:
        assert self.app.search_tools
        selected = self.app.view.index_tab.index_dataset_table.selection()
        if not selected:
            return
        answer = messagebox.askyesno(_("提示"), _("你确定要删除选中目录吗？"))
        if not answer:
            return
        self.__is_updating = True
        self.__check_queue()
        dirs_to_delete = []
        search_dirs: list = self.app.setting.model.index.search_dir
        for item in selected:
            delete_search_dir = self.app.view.index_tab.index_dataset_table.item(item, 'values')[1]
            dirs_to_delete.append(delete_search_dir)
            search_dirs.remove(delete_search_dir)
            self.app.view.index_tab.index_dataset_table.delete(item)
        self.refresh_index_dataset_table()
        remaining_dirs = [d for d in self.app.setting.model.index.search_dir]
        for dir_path in dirs_to_delete:
            self.app.search_tools.remove_files_in_directory(dir_path, remaining_dirs)
        self.app.search_tools.remove_nonexists()
        self.app.setting.save()
        self.__is_updating = False
        self.app.view.after(1000, self.update_index_tip)

    def __toggle_auto_update(self) -> None:
        enabled = self.app.view.index_tab.auto_update_checkbutton.instate(['selected'])
        self.app.setting.app.auto_update_index = enabled
        if enabled:
            if not hasattr(self, 'idle_tracker'):
                self.idle_tracker = idle_tracker.IdleMonitor(
                    root=self.app.view,
                    threshold=self.app.setting.app.auto_update_idle_threshold,
                    on_idle=lambda: self.__sync_index(auto=True),
                )
                self.idle_tracker.start()
        else:
            if hasattr(self, 'idle_tracker'):
                self.idle_tracker.stop()
                del self.idle_tracker
            if self.is_auto_updating and self.app.search_tools:
                self.app.search_tools.force_stop_update = True

    @decorators.send_task
    def __clean_excluded(self) -> None:
        assert self.app.search_tools
        search_dirs = self.app.setting.model.index.search_dir
        rules = self.app.setting.model.index.exclude_rules or []
        if not rules:
            messagebox.showinfo(_("提示"), _("当前没有设置排除规则。"))
            return
        if not search_dirs:
            messagebox.showinfo(_("提示"), _("当前没有索引目录。"))
            return
        if self.__is_updating:
            messagebox.showinfo(_("提示"), _("索引正在更新中，禁用排除图片清理！"))
            return
        if self._is_cleaning:
            return
        self._is_cleaning = True
        try:
            tip = self.app.view.index_tab.index_tip_label
            tip.after(0, lambda: tip.config(text=_("正在检查排除文件...")))
            excluded = self.app.search_tools.get_excluded_files(rules, search_dirs)
            tip.after(0, lambda: tip.config(text=_("检查完成。")))

            if not excluded:
                messagebox.showinfo(_("提示"), _("索引中没有匹配排除规则的文件。"))
                return

            if not messagebox.askyesno(
                _("确认清理"),
                _("将在索引中移除 {count} 个匹配排除规则的文件记录。\n\n此操作不可撤消，是否继续？", count=len(excluded))
            ):
                return
            if self.__is_updating:
                messagebox.showinfo(_("提示"), _("索引正在更新中，禁用排除图片清理！"))
                return
            self.app.search_tools.remove_files(excluded)
            self.app.search_tools.remove_nonexists()
            messagebox.showinfo(_("提示"), _("已清理 {count} 个文件记录。", count=len(excluded)))
        finally:
            self.update_index_tip()
            self._is_cleaning = False

    def __check_queue(self) -> None:
        try:
            while True:
                message = decorators.progress_queue.get_nowait()
                self.app.view.index_tab.index_tip_label.config(text=message)
        except Exception as e:
            logging.warning(f"__check_queue 异常: {e}")
        if self.__is_updating:
            self.app.view.after(200, self.__check_queue)
