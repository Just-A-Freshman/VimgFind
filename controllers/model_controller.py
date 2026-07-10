from __future__ import annotations

import zipfile
from pathlib import Path
from tkinter import filedialog, messagebox
from ttkbootstrap import Entry
from typing import TYPE_CHECKING, Callable, cast
import tkinter as tk

from config.types import ModelConfig
from config.settings import STATUS_LABEL, TYPE_LABEL
from core import SearchTool
import utils.file_ops as file_ops
import utils.model_checker as model_checker

if TYPE_CHECKING:
    from .app_controller import AppController
    from views.model_page import ModelFrame



class ModelController:
    def __init__(self, app_controller: AppController) -> None:
        self.app = app_controller
        self._model_cache: dict[str, ModelConfig] = {}
        self._editing_model_id: str | None = None
        self._current_download: model_checker.DownloadTask | None = None

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
                file_ops.format_bytes(cfg.meta.size),
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

        if self.app.index_controller.is_updating:
            view.use_btn.config(state=tk.DISABLED)
            view.uninstall_btn.config(state=tk.DISABLED)

        if self._current_download and self._current_download.model_id == iid:
            view.download_btn.place_forget()
            self._show_download_progress(view)
            self._update_download_progress(
                view,
                self._current_download.downloaded_bytes,
                self._current_download.total_bytes,
                self._current_download.speed,
            )

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

    def switch_model(self, model_id: str = "", resend_search: bool = False) -> None:
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
        self.app.search_tools = SearchTool(self.app.setting)
        if resend_search:
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

        self._remove_model(model_id)
        self._update_tree_status(model_id, "not download")
        combobox = self.app.view.index_tab.switch_model_combobox
        values = list(combobox.cget("values"))
        if cfg.meta.name in values:
            values.remove(cfg.meta.name)
            combobox.config(values=values)

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

        if self._current_download is not None and self._current_download.state in (
            model_checker.DownloadState.DOWNLOADING, model_checker.DownloadState.PAUSED,
        ):
            return

        model_id = cfg.meta.id or iid
        self._current_download = model_checker.DownloadTask(
            url=cfg.meta.download_url,
            dest_dir=self.app.setting.models_dir / model_id,
            model_id=model_id,
            checksum=cfg.meta.checksum_sha256,
        )
        self._current_download.start(progress_callback=self._make_progress_callback(view))
        self._show_download_progress(view)
        self._update_tree_status(model_id, "downloading")
        self._poll_download(view, model_id)

    def on_download_control(self) -> None:
        task = self._current_download
        if task is None:
            return
        btn = self.app.view.model_tab.download_control_btn
        if task.state == model_checker.DownloadState.DOWNLOADING:
            task.pause()
            btn.config(text="继续")
        elif task.state == model_checker.DownloadState.PAUSED:
            task.resume()
            btn.config(text="暂停")

    def on_download_cancel(self) -> None:
        task = self._current_download
        if task is None:
            return
        task.cancel()
        model_id = task.model_id
        self._current_download = None
        self._finish_download(False, True, model_id, self.app.view.model_tab)

    def load_local_model(self, file_path: str = "") -> None:
        if not file_path:
            file_path = filedialog.askopenfilename(title="选择模型文件", filetypes=[("ZIP files", "*.zip"), ("All files", "*.*")])
            if not file_path:
                return

        zip_path = Path(file_path)
        model_id = zip_path.stem

        if model_checker.is_installed(self.app.setting, model_id):
            answer = messagebox.askyesno("提示", f"模型「{model_id}」已安装，是否覆盖？")
            if not answer:
                return

        fresh = model_checker.fetch_remote_manifest(
            url=self.app.setting.app.remote_manifest_url,
            cache_path=self.app.setting.manifest_cache,
            cache_ttl=0,
        )
        entry = next((entry for entry in fresh if entry.get("meta_info", {}).get("id") == model_id), None) if fresh else None

        if entry:
            expected_cs = (entry.get("meta_info") or {}).get("checksum_sha256", "")
            if expected_cs and not model_checker.verify_zip_sha256(zip_path, expected_cs):
                messagebox.showerror(
                    "校验失败",
                    f"校验和不匹配，存在模型 ID 冲突风险！\n\n"
                    f"文件「{zip_path.name}」的校验和与远程记录不匹配，\n"
                    f"可能是文件损坏或被篡改，请勿加载。"
                )
                return
            cfg = ModelConfig.from_dict(entry)
        else:
            try:
                cfg = model_checker.validate_unknown_zip(zip_path, model_id)
                if cfg is None:
                    return
            except AssertionError as e:
                messagebox.showerror("错误", str(e))
                return

        self._load_model_from_zip(zip_path, model_id, cfg)

    def _load_model_from_zip(self, zip_path: Path, model_id: str, cfg: ModelConfig) -> None:
        dest_dir = self.app.setting.models_dir / model_id
        try:
            if dest_dir.exists():
                file_ops.rmtree(dest_dir)
            dest_dir.mkdir(parents=True, exist_ok=True)

            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(dest_dir)

            self.app.setting.save_model_config(model_id, cfg)
            self.load_model_list()
            messagebox.showinfo("提示", f"模型「{model_id}」加载成功！")
        except Exception as e:
            messagebox.showerror("错误", f"加载模型失败：{e}")
            if dest_dir.exists():
                file_ops.rmtree(dest_dir)

    def _make_progress_callback(self, view) -> Callable:
        return lambda downloaded, total, speed: view.after(
            0, lambda: self._update_download_progress(view, downloaded, total, speed)
        )

    def _poll_download(self, view, model_id: str) -> None:
        task = self._current_download
        if task is None:
            return
        if task.state in (model_checker.DownloadState.COMPLETED, model_checker.DownloadState.ERROR, model_checker.DownloadState.CANCELLED):
            success = task.state == model_checker.DownloadState.COMPLETED
            cancelled = task.state == model_checker.DownloadState.CANCELLED
            self._finish_download(success, cancelled, model_id, view)
            self._current_download = None
            return
        view.after(200, lambda: self._poll_download(view, model_id))

    def _show_download_progress(self, view: ModelFrame) -> None:
        view.download_btn.place_forget()
        view.download_progress_label.config(text="准备下载...")
        view.download_progressbar.config(value=0)
        view.download_progress_label.place(relx=0.05, rely=0.87, relwidth=0.50, anchor=tk.W)
        is_paused = self._current_download and self._current_download.state == model_checker.DownloadState.PAUSED
        view.download_control_btn.config(text="继续" if is_paused else "暂停")
        view.download_control_btn.place(relx=0.62, rely=0.87, anchor=tk.W)
        view.download_cancel_btn.place(relx=0.78, rely=0.87, anchor=tk.W)
        view.download_progressbar.place(relx=0.5, rely=0.92, relwidth=0.9, anchor=tk.CENTER)

    def _update_download_progress(self, view: ModelFrame, downloaded: int, total: int, speed: float) -> None:
        if total > 0:
            view.download_progressbar.config(value=int(downloaded * 100 / total))
        view.download_progress_label.config(
            text=f"{file_ops.format_bytes(speed, as_speed=True)} - {file_ops.format_bytes(downloaded)}/{file_ops.format_bytes(total)}"
        )

    def _hide_download_ui(self, view: ModelFrame) -> None:
        view.download_progressbar.place_forget()
        view.download_progress_label.place_forget()
        view.download_control_btn.place_forget()
        view.download_cancel_btn.place_forget()

    def _update_tree_status(self, model_id: str, status: str) -> None:
        view = self.app.view.model_tab
        if model_id in view.model_tree.get_children(""):
            view.model_tree.set(model_id, "状态", STATUS_LABEL.get(status, status))

    def _get_model_status(self, model_id: str) -> str:
        if self._current_download and self._current_download.model_id == model_id:
            return "downloading"
        if model_id == self.app.setting.app.current_model:
            return "using"
        if model_checker.is_installed(self.app.setting, model_id):
            return "downloaded"
        return "not download"

    def _remove_model(self, model_id: str) -> None:
        model_dir = self.app.setting.models_dir / model_id
        file_ops.rmtree(model_dir)
        self._model_cache.pop(model_id, None)
        self.app.setting.remove_model_config(model_id)
        self.load_model_list()
        self.app.view.model_tab.show_default()

    def _finish_download(self, success: bool, cancelled: bool, model_id: str, view: ModelFrame) -> None:
        if cancelled:
            self._remove_model(model_id)
            return
        self._hide_download_ui(view)
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
                self._remove_model(model_id)
            messagebox.showerror("下载失败", f"模型「{model_id}」下载失败，请检查网络后重试。")
            self.on_model_select()
