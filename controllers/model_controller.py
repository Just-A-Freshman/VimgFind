from __future__ import annotations

import shutil
import time
from tkinter import messagebox
from ttkbootstrap import Entry
from typing import TYPE_CHECKING, Literal, cast
import tkinter as tk

from config.types import ModelConfig
from config.settings import STATUS_LABEL, TYPE_LABEL
from core import SearchTool
import utils.file_ops as file_ops
import utils.model_checker as model_checker
import utils.decorators as decorators

if TYPE_CHECKING:
    from .app_controller import AppController
    from views.model_page import ModelFrame




def _format_size(size_bytes: int) -> str:
    if size_bytes >= 1024 ** 3:
        return f"{size_bytes / 1024 ** 3:.1f}GB"
    if size_bytes >= 1024 ** 2:
        return f"{size_bytes / 1024 ** 2:.0f}MB"
    if size_bytes >= 1024:
        return f"{size_bytes / 1024:.0f}KB"
    return f"{size_bytes}B"


def _format_speed(bytes_per_sec: float) -> str:
    if bytes_per_sec >= 1024 ** 3:
        return f"{bytes_per_sec / 1024 ** 3:.2f}GB/s"
    if bytes_per_sec >= 1024 ** 2:
        return f"{bytes_per_sec / 1024 ** 2:.2f}MB/s"
    if bytes_per_sec >= 1024:
        return f"{bytes_per_sec / 1024:.1f}KB/s"
    return f"{bytes_per_sec:.1f}B/s"


class ModelController:
    def __init__(self, app_controller: AppController) -> None:
        self.app = app_controller
        self._model_cache: dict[str, ModelConfig] = {}
        self._editing_model_id: str | None = None
        self._downloading_model_id: str | None = None
        self._dl_downloaded: int = 0
        self._dl_total: int = 0
        self._dl_speed: float = 0.0

    def load_model_list(self):
        view = self.app.view.model_tab
        self._model_cache.clear()
        view.model_tree.delete(*view.model_tree.get_children())

        models = model_checker.get_available_models(self.app.setting)
        for cfg in models:
            model_id = cfg.meta.id or cfg.meta.name
            status = self._get_model_status(model_id)
            self._model_cache[model_id] = cfg
            view.model_tree.insert("", tk.END, iid=model_id, values=(
                cfg.meta.name or model_id,
                cfg.meta.label or "",
                TYPE_LABEL.get(cfg.meta.model_type, cfg.meta.model_type),
                _format_size(cfg.meta.size),
                STATUS_LABEL.get(status, status),
            ))

    def get_downloaded_models(self) -> list[ModelConfig]:
        return [
            cfg for model_id, cfg in self._model_cache.items()
            if self._get_model_status(model_id) != "not download"
        ]

    def on_model_select(self, event=None) -> None:
        view = self.app.view.model_tab
        selection = view.model_tree.selection()
        if not selection:
            return
        iid = selection[0]
        if not iid:
            view.show_default()
            return
        cfg = self._model_cache.get(iid)
        if cfg is None:
            view.show_default()
            return
        self._editing_model_id = iid
        view.show_detail(cfg)

        if iid == self._downloading_model_id:
            view.download_btn.place_forget()
            self._show_download_progress(view)
            if self._dl_total > 0:
                self._update_download_progress(view, self._dl_downloaded, self._dl_total, self._dl_speed)

    def on_name_edited(self, event: tk.Event) -> None:
        name_entry = cast(Entry, event.widget)
        new_name = name_entry.get().strip()
        if not new_name:
            return

        iid = self._editing_model_id
        if not iid:
            return
        values = list(self.app.view.model_tab.model_tree.item(iid, "values"))
        values[0] = new_name
        self.app.view.model_tab.model_tree.item(iid, values=values)
        cfg = self._model_cache.get(iid)
        if cfg is not None:
            old_name = cfg.meta.name
            cfg.meta.name = new_name
            self.app.setting.save_model_config(iid, cfg)

            combobox = self.app.view.index_tab.switch_model_combobox
            values = list(combobox.cget("values"))
            for i, v in enumerate(values):
                if v == old_name:
                    values[i] = new_name
                    break
            combobox.config(values=values)
            if combobox.get() == old_name:
                combobox.set(new_name)

    def _show_download_progress(self, view: ModelFrame) -> None:
        view.download_btn.place_forget()
        view.download_progress_label.config(text="准备下载...")
        view.download_progressbar.config(value=0)
        view.download_progress_label.place(relx=0.02, rely=0.82, relwidth=0.96, anchor=tk.W)
        view.download_progressbar.place(relx=0.5, rely=0.92, relwidth=0.9, anchor=tk.CENTER)

    def _update_download_progress(self, view: ModelFrame, downloaded: int, total: int, speed: float) -> None:
        self._dl_downloaded = downloaded
        self._dl_total = total
        self._dl_speed = speed
        if total > 0:
            view.download_progressbar.config(value=int(downloaded * 100 / total))
        view.download_progress_label.config(
            text=f"{_format_speed(speed)} - {_format_size(downloaded)}/{_format_size(total)}"
        )

    def _update_tree_status(self, model_id: str, status: Literal["using", "downloaded", "not download"]) -> None:
        view = self.app.view.model_tab
        if model_id in view.model_tree.get_children(""):
            view.model_tree.set(model_id, "状态", STATUS_LABEL.get(status, status))

    def _get_model_status(self, model_id: str) -> Literal["using", "downloaded", "not download"]:
        if model_id == self.app.setting.app.current_model:
            return "using"
        if model_checker.is_installed(self.app.setting, model_id):
            return "downloaded"
        return "not download"

    def on_model_double_click(self, event=None) -> None:
        selection = self.app.view.model_tab.model_tree.selection()
        if not selection:
            return
        iid = selection[0]
        cfg = self._model_cache.get(iid)
        if cfg is None:
            return
        model_id = cfg.meta.id or iid
        model_json_path = self.app.setting.models_dir / model_id / "model.json"
        if model_json_path.exists():
            file_ops.open_file(model_json_path)

    def switch_model(self, model_id: str = "") -> None:
        self.app.setting.save()
        self.app.view.model_tab.use_btn.config(state=tk.DISABLED)
        model_id = model_id if model_id else self.app.view.model_tab.model_tree.selection()[0]
        old_model_id = self.app.setting.app.current_model
        if model_id == old_model_id:
            return
        if self.app.search_tools:
            self.app.search_tools.save_index()
            self.app.search_tools.destroy(wait=True)
        self.app.setting.app.current_model = model_id
        self.app.search_tools = SearchTool(self.app.setting, model_id)
        self.app.search_controller.resend_last_search()
        self.app.view.index_tab.switch_model_combobox.set(self._model_cache[model_id].meta.name)
        self.app.index_controller.refresh_index_dataset_table()
        self.app.view.after(100, self.app.index_controller.update_index_tip)
        self.app.view.title(f"VimgFind - {self._model_cache[model_id].meta.name}")
        self._update_tree_status(old_model_id, "downloaded")
        self._update_tree_status(model_id, "using")
        self.app.view.model_tab.model_tree.selection_set(model_id)
        self.on_model_select()

    def uninstall_model(self) -> None:
        view = self.app.view.model_tab
        iid = view.model_tree.selection()[0]
        if not iid:
            return
        cfg = self._model_cache.get(iid)
        if cfg is None:
            return
        model_id = cfg.meta.id or iid

        if not model_checker.is_installed(self.app.setting, model_id):
            return

        answer = messagebox.askyesno("确认卸载", f"确定要卸载模型「{cfg.meta.name or model_id}」吗？\n该模型对应的索引也会被删除！", icon=messagebox.WARNING)
        if not answer:
            return

        model_dir = self.app.setting.models_dir / model_id
        
        try:
            shutil.rmtree(model_dir)
        except Exception as e:
            messagebox.showerror("卸载失败", str(e))
            return

        view.model_tree.delete(iid)
        self._model_cache.pop(iid, None)
        self.app.setting._model_cache.pop(iid, None)
        combobox = self.app.view.index_tab.switch_model_combobox
        values = list(combobox.cget("values"))
        if cfg.meta.name in values:
            values.remove(cfg.meta.name)
            combobox.config(values=values)
        view.show_default()

    @decorators.send_task
    def download_model(self) -> None:
        view = self.app.view.model_tab
        iid = view.model_tree.selection()[0]
        if not iid:
            return
        cfg = self._model_cache.get(iid)
        if cfg is None:
            return
        if not cfg.meta.download_url:
            messagebox.showinfo("提示", "该模型没有可用的下载地址。")
            return

        model_id = cfg.meta.id or iid
        self._downloading_model_id = model_id
        url = cfg.meta.download_url
        checksum = cfg.meta.checksum_sha256

        # 切换到进度显示（主线程）
        view.after(0, lambda: self._show_download_progress(view))

        # 进度跟踪状态
        _last_ui = [0.0]
        _speed_state: dict = {"last_dl": 0, "last_time": time.time(), "speed": 0.0}

        def _progress(downloaded: int, total: int) -> None:
            now = time.time()
            elapsed = now - _speed_state["last_time"]
            delta = downloaded - _speed_state["last_dl"]
            if elapsed > 0.1:
                _speed_state["speed"] = delta / elapsed
            _speed_state["last_dl"] = downloaded
            _speed_state["last_time"] = now

            if now - _last_ui[0] < 0.1:
                return
            _last_ui[0] = now

            view.after(
                0,
                lambda d=downloaded, t=total, s=_speed_state["speed"]:
                self._update_download_progress(view, d, t, s),
            )

        dest_dir = self.app.setting.models_dir / model_id
        success = model_checker.download_and_extract_zip(
            url=url,
            dest_dir=dest_dir,
            checksum=checksum,
            progress_callback=_progress,
        )

        view.after(0, self._finish_download, success, model_id, view)

    def _finish_download(self, success: bool, model_id: str, view: ModelFrame) -> None:
        self._downloading_model_id = None
        view.download_progressbar.place_forget()
        view.download_progress_label.place_forget()
        view.use_btn.config(state=tk.NORMAL)
        view.uninstall_btn.config(state=tk.NORMAL)
        if success:
            self._update_tree_status(model_id, "downloaded")
            cfg = self._model_cache.get(model_id)
            if cfg:
                self.app.setting.save_model_config(model_id, cfg)
                combobox = self.app.view.index_tab.switch_model_combobox
                values = list(combobox.cget("values"))
                values.append(cfg.meta.name)
                combobox.config(values=values)
            if model_id in view.model_tree.get_children(""):
                view.model_tree.selection_set(model_id)
                self.on_model_select()
        else:
            is_installed_anyway = model_id in self._model_cache and model_checker.is_installed(
                self.app.setting, model_id
            )
            if not is_installed_anyway:
                model_dir = self.app.setting.models_dir / model_id
                
                try:
                    shutil.rmtree(model_dir)
                except Exception:
                    pass
            messagebox.showerror("下载失败", f"模型「{model_id}」下载失败，请检查网络后重试。")
            self.on_model_select()
