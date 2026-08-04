from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Callable, cast
from tkinter import filedialog, messagebox
import tkinter as tk
import zipfile
import logging
import time
import json

from ttkbootstrap import Entry

from core import SearchTool
from config.settings import ACTIVE_MARKER, TYPE_LABEL, TkS
from config.types import ModelConfig
from utils.i18n import _
import utils.file_ops as file_ops
import utils.internet as internet

if TYPE_CHECKING:
    from .app_controller import AppController
    from views.model_page import ModelFrame


class ModelController:
    def __init__(self, app_controller: AppController) -> None:
        self.app = app_controller
        self.model_checker = ModelChecker(app_controller)
        self._model_cache: dict[str, ModelConfig] = {}
        self.__editing_model_id: str | None = None
        self.__current_download: internet.DownloadTask | None = None

    def env_init(self) -> None:
        self.__load_model_list()
        self.__on_theme_change()
        tab = self.app.view.model_tab
        tab.model_tree.bind("<<TreeviewSelect>>", self.on_model_select)
        tab.model_tree.bind("<Double-Button-1>", self.__on_model_double_click)
        tab.name_edit_entry.bind("<FocusOut>", self.__on_name_edited)
        tab.model_tree.bind("<<ThemeChanged>>", lambda e: self.__on_theme_change())
        tab.use_btn.config(command=self.switch_model)
        tab.uninstall_btn.config(command=self.__uninstall_model)
        tab.download_btn.config(command=self.__download_model)
        tab.download_control_btn.config(command=self.__on_download_control)
        tab.download_cancel_btn.config(command=self.__on_download_cancel)
        tab.browser_button.config(command=self.load_local_model)

    def get_downloaded_models(self) -> list[ModelConfig]:
        return [
            cfg for model_id, cfg in self._model_cache.items()
            if self.get_model_status(model_id) != "not download"
        ]

    def get_model_status(self, model_id: str) -> str:
        if self.__current_download and self.__current_download.model_id == model_id:
            return "downloading"
        if model_id == self.app.setting.app.current_model:
            return "using"
        if self.model_checker.is_installed(model_id):
            return "downloaded"
        return "not download"

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
        self.__editing_model_id = iid
        view.show_detail(cfg)

        if self.app.index_controller.is_updating:
            view.use_btn.config(state=tk.DISABLED)
            view.uninstall_btn.config(state=tk.DISABLED)

        if self.__current_download and self.__current_download.model_id == iid:
            view.download_btn.grid_forget()
            self.__show_download_progress()
            self.__update_download_progress(
                self.__current_download.downloaded_bytes,
                self.__current_download.total_bytes,
                self.__current_download.speed,
            )

    def load_local_model(self, file_path: str = "") -> None:
        if not file_path:
            file_path = filedialog.askopenfilename(title=_("选择模型文件"), filetypes=[("ZIP files", "*.zip"), ("All files", "*.*")])
            if not file_path:
                return

        zip_path = Path(file_path)
        model_id = zip_path.stem

        if self.model_checker.is_installed(model_id):
            answer = messagebox.askyesno(_("提示"), _("模型「{id}」已安装，是否覆盖？", id=model_id))
            if not answer:
                return

        fresh = self.model_checker.fetch_remote_manifest(cache_ttl=0)
        entry = next((entry for entry in fresh if entry.get("meta_info", {}).get("id") == model_id), None) if fresh else None

        if entry:
            expected_cs = (entry.get("meta_info") or {}).get("checksum_sha256", "")
            if expected_cs and not file_ops.verify_file_sha256(zip_path, expected_cs):
                messagebox.showerror(
                    _("校验失败"),
                    _("校验和不匹配，存在模型 ID 冲突风险！\n\n文件「{name}」的校验和与远程记录不匹配，\n可能是文件损坏或被篡改，请勿加载。",
                        name=zip_path.name)
                )
                return
            cfg = ModelConfig.from_dict(entry)
        else:
            try:
                cfg = self.model_checker.validate_unknown_zip(zip_path, model_id)
                if cfg is None:
                    return
            except AssertionError as e:
                messagebox.showerror(_("错误"), str(e))
                return

        self.__load_model_from_zip(zip_path, model_id, cfg)

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
        self.__update_tree_status(old_model_id, "downloaded")
        self.__update_tree_status(model_id, "using")
        self.app.view.model_tab.model_tree.selection_set(model_id)
        self.on_model_select()

    def __load_model_list(self) -> None:
        view = self.app.view.model_tab
        self._model_cache.clear()
        view.model_tree.delete(*view.model_tree.get_children())

        models = self.model_checker.get_available_models()
        for cfg in models:
            model_id = cfg.meta.id or cfg.meta.name
            status = self.get_model_status(model_id)
            self._model_cache[model_id] = cfg
            name = cfg.meta.name or model_id
            if status == "using":
                name = f"{ACTIVE_MARKER}{name}"
            view.model_tree.insert("", tk.END, iid=model_id, values=(
                name,
                cfg.meta.label or "",
                _(TYPE_LABEL.get(cfg.meta.model_type, cfg.meta.model_type)),
                file_ops.format_bytes(cfg.meta.size, decimal_parts={'MB': 0, "KB": 0}),
            ), tags=(status,))

    def __on_theme_change(self):
        tab = self.app.view.model_tab
        active_fg = self.app.view.style.colors.get("info")   #type:ignore
        tab.model_tree.tag_configure("downloaded", foreground=active_fg)
        tab.model_tree.tag_configure("using", foreground=active_fg)

    def __on_name_edited(self, event: tk.Event) -> None:
        name_entry = cast(Entry, event.widget)
        new_name = name_entry.get().strip()
        if not new_name:
            return

        iid = self.__editing_model_id
        if not iid:
            return
        tree = self.app.view.model_tab.model_tree
        tags = tree.item(iid, "tags")
        values = list(tree.item(iid, "values"))
        values[0] = f"{ACTIVE_MARKER}{new_name}" if tags and tags[0] == "using" else new_name
        tree.item(iid, values=values)
        cfg = self._model_cache.get(iid)
        if cfg is None:
            return
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

    def __on_model_double_click(self, event=None) -> None:
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

    def __uninstall_model(self) -> None:
        view = self.app.view.model_tab
        iid = view.model_tree.selection()[0]
        if not iid:
            return
        cfg = self._model_cache.get(iid)
        if cfg is None:
            return
        model_id = cfg.meta.id or iid

        if not self.model_checker.is_installed(model_id):
            return

        answer = messagebox.askyesno(_("确认卸载"), _("确定要卸载模型「{name}」吗？\n该模型对应的索引也会被删除！", name=cfg.meta.name or model_id), icon=messagebox.WARNING)
        if not answer:
            return

        self.__remove_model(model_id)
        self.__update_tree_status(model_id, "not download")
        combobox = self.app.view.index_tab.switch_model_combobox
        values = list(combobox.cget("values"))
        if cfg.meta.name in values:
            values.remove(cfg.meta.name)
            combobox.config(values=values)

    def __download_model(self) -> None:
        view = self.app.view.model_tab
        iid = view.model_tree.selection()[0]
        if not iid:
            return
        cfg = self._model_cache.get(iid)
        if cfg is None:
            return
        if not cfg.meta.download_url:
            messagebox.showinfo(_("提示"), _("该模型没有可用的下载地址。"))
            return

        if self.__current_download is not None and self.__current_download.state in (
            internet.DownloadState.DOWNLOADING, internet.DownloadState.PAUSED,
        ):
            return

        model_id = cfg.meta.id or iid
        self.__current_download = internet.DownloadTask(
            url=cfg.meta.download_url,
            dest_dir=self.app.setting.models_dir / model_id,
            model_id=model_id,
            checksum=cfg.meta.checksum_sha256,
        )        
        self.__current_download.start(progress_callback=lambda d, t, s: self.__update_download_progress(d, t, s))
        self.__show_download_progress()
        self.__update_tree_status(model_id, "downloading")
        self.__poll_download(model_id)

    def __on_download_control(self) -> None:
        task = self.__current_download
        if task is None:
            return
        btn = self.app.view.model_tab.download_control_btn
        if task.state == internet.DownloadState.DOWNLOADING:
            task.pause()
            btn.config(text=_("继续"))
        elif task.state == internet.DownloadState.PAUSED:
            task.resume()
            btn.config(text=_("暂停"))

    def __on_download_cancel(self) -> None:
        task = self.__current_download
        if task is None:
            return
        task.cancel()
        model_id = task.model_id
        self.__current_download = None
        self.__finish_download(False, True, model_id, self.app.view.model_tab)

    def __load_model_from_zip(self, zip_path: Path, model_id: str, cfg: ModelConfig) -> None:
        dest_dir = self.app.setting.models_dir / model_id
        try:
            if dest_dir.exists():
                file_ops.rmtree(dest_dir)
            dest_dir.mkdir(parents=True, exist_ok=True)

            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(dest_dir)

            self.app.setting.save_model_config(model_id, cfg)
            self.__load_model_list()
            messagebox.showinfo(_("提示"), _("模型「{id}」加载成功！", id=model_id))
        except Exception as e:
            messagebox.showerror(_("错误"), _("加载模型失败：{e}", e=str(e)))
            if dest_dir.exists():
                file_ops.rmtree(dest_dir)

    def __poll_download(self, model_id: str) -> None:
        view = self.app.view.model_tab
        task = self.__current_download
        if task is None:
            return
        if task.state in (internet.DownloadState.COMPLETED, internet.DownloadState.ERROR, internet.DownloadState.CANCELLED):
            success = task.state == internet.DownloadState.COMPLETED
            cancelled = task.state == internet.DownloadState.CANCELLED
            self.__finish_download(success, cancelled, model_id, view)
            self.__current_download = None
            return
        view.after(200, lambda: self.__poll_download(model_id))

    def __show_download_progress(self) -> None:
        view = self.app.view.model_tab
        view.download_btn.grid_forget()
        view.btn_group.grid_forget()
        view.download_progress_label.config(text=_("准备下载..."))
        view.download_progressbar.config(value=0)
        is_paused = self.__current_download and self.__current_download.state == internet.DownloadState.PAUSED
        view.download_control_btn.config(text=_("继续") if is_paused else _("暂停"))

        view.download_progress_label.grid(row=0, column=0, sticky=tk.W, padx=(TkS(5), TkS(2)), pady=(TkS(3), TkS(3)))
        view.download_control_btn.grid(row=0, column=1, sticky=tk.E)
        view.download_cancel_btn.grid(row=0, column=2, sticky=tk.E, padx=(TkS(2), TkS(5)))
        view.download_progressbar.grid(row=1, column=0, columnspan=3, sticky=tk.EW, padx=TkS(5), pady=(0, TkS(5)))

    def __update_download_progress(self, downloaded: int, total: int, speed: float) -> None:
        view = self.app.view.model_tab
        if total > 0:
            view.download_progressbar.config(value=int(downloaded * 100 / total))
        view.download_progress_label.config(
            text=f"{file_ops.format_bytes(speed)}/s - {file_ops.format_bytes(downloaded)}/{file_ops.format_bytes(total)}"
        )

    def __update_tree_status(self, model_id: str, status: str) -> None:
        view = self.app.view.model_tab
        if model_id in view.model_tree.get_children(""):
            tree = view.model_tree
            values = list(tree.item(model_id, "values"))
            name = values[0].removeprefix(ACTIVE_MARKER)
            values[0] = f"{ACTIVE_MARKER}{name}" if status == "using" else name
            tree.item(model_id, values=values, tags=(status,))

    def __remove_model(self, model_id: str) -> None:
        model_dir = self.app.setting.models_dir / model_id
        file_ops.rmtree(model_dir)
        self._model_cache.pop(model_id, None)
        self.app.setting.remove_model_config(model_id)
        self.__load_model_list()
        self.app.view.model_tab.show_default()

    def __finish_download(self, success: bool, cancelled: bool, model_id: str, view: ModelFrame) -> None:
        if cancelled:
            self.__remove_model(model_id)
            return
        view.download_progressbar.grid_forget()
        view.download_progress_label.grid_forget()
        view.download_control_btn.grid_forget()
        view.download_cancel_btn.grid_forget()
        view.use_btn.config(state=tk.NORMAL)
        view.uninstall_btn.config(state=tk.NORMAL)
        if success:
            self.__update_tree_status(model_id, "downloaded")
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
            is_installed_anyway = model_id in self._model_cache and self.model_checker.is_installed(model_id)
            if not is_installed_anyway:
                self.__remove_model(model_id)
            messagebox.showerror(_("下载失败"), _("模型「{id}」下载失败，请检查网络后重试。", id=model_id))
            self.on_model_select()


class ModelChecker:
    def __init__(self, app_controller: AppController) -> None:
        self.app = app_controller

    def validate_unknown_zip(self, zip_path: Path, model_id: str) -> ModelConfig:
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                namelist = zf.namelist()

                onnx_files = [n for n in namelist if n.endswith(".onnx")]
                if not onnx_files:
                    raise AssertionError("无法识别的模型包：未找到 ONNX 模型文件（.onnx）。")

                if "model.json" not in namelist:
                    raise AssertionError("无法识别的模型包：未找到 model.json 配置文件。")

                with zf.open("model.json") as f:
                    raw = json.loads(f.read().decode("utf-8"))

                mc = raw.get("model_config") or {}
                image_path = mc.get("image_encoder_path", "") or ""
                text_path = mc.get("text_encoder_path", "") or ""

                if image_path and image_path not in namelist:
                    raise AssertionError(f"校验失败：model.json 中的 image_encoder_path「{image_path}」在 zip 包中不存在。")
                if text_path and text_path not in namelist:
                    raise AssertionError(f"校验失败：model.json 中的 text_encoder_path「{text_path}」在 zip 包中不存在。")

                raw["meta_info"] = raw.get("meta_info") or {"id": model_id, "name": model_id}
                return ModelConfig.from_dict(raw)

        except (zipfile.BadZipFile, json.JSONDecodeError) as e:
            raise AssertionError(f"无法读取模型包：{e}")

    def fetch_remote_manifest(self, cache_ttl: int = 0) -> list[dict] | None:
        now = time.time()
        cache_path = self.app.setting.manifest_cache
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cache = json.load(f)
        except (json.JSONDecodeError, IOError, FileNotFoundError):
            cache = {}
        if now - cache.get("timestamp", 0) < max(cache_ttl, 0):
            return cache.get("models")
        try:
            with internet.fetch_url(self.app.setting.app.remote_manifest_url, timeout=5, validate=True) as resp:
                models: list[dict] = json.loads(json.loads(resp.read().decode("utf-8"))["raw_content"])

            cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump({"timestamp": now, "models": models}, f, indent=2)
            return models
        except (OSError, ValueError, json.JSONDecodeError) as e:
            logging.error(f"获取远程模型失败：{str(e)}")
            return cache.get("models")

    def is_installed(self, model_id: str) -> bool:
        model_dir = self.app.setting.models_dir / model_id
        return model_dir.is_dir() and (model_dir / "model.json").is_file()

    def get_available_models(self) -> list[ModelConfig]:
        installed_ids = self.app.setting.get_model_list()
        local_map: dict[str, ModelConfig] = {}
        result: list[ModelConfig] = []

        for mid in installed_ids:
            cfg = self.app.setting.load_model_config(mid)
            local_map[mid] = cfg
            result.append(cfg)

        remote_raw = self.fetch_remote_manifest(self.app.setting.app.cache_ttl)
        if not remote_raw:
            return result
        for entry in remote_raw:
            meta = entry.get("meta_info") or {}
            mid = meta.get("id")
            if not mid:
                continue
            if mid in local_map:
                disk_cfg = local_map[mid]
                if not disk_cfg.meta.download_url:
                    disk_cfg.meta.download_url = meta.get("download_url", "")
                if not disk_cfg.meta.checksum_sha256:
                    disk_cfg.meta.checksum_sha256 = meta.get("checksum_sha256", "")
            else:
                result.append(ModelConfig.from_dict(entry))

        return result

