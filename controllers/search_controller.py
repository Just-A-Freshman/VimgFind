from __future__ import annotations

from tkinter import filedialog, messagebox
from typing import TYPE_CHECKING, Literal
from pathlib import Path
import linecache
import datetime
import logging
import os
import tkinter as tk

from PIL import Image

from settings import Setting
import utils.file_ops as file_ops
import utils.image_ops as image_ops
import utils.decorators as decorators
from views.widgets import DetailListView, ThumbnailGridView
from core import SearchStatus

if TYPE_CHECKING:
    from .app_controller import AppController


class SearchController(object):
    def __init__(self, app_controller: AppController) -> None:
        self._last_search_content: Image.Image | str = ""
        self._is_finish_search: bool = True
        self._preview_timer: str | None = None
        self.similarity_threshold: float = 0.0
        self.app = app_controller
        self._queue_index: int = 0
        self._queue_total: int = 0
        self._nav_debounce_timer: str | None = None

    @decorators.send_task
    def search_by_browser(self, image_paths: str | list[str] | None = None) -> None:
        if isinstance(image_paths, str):
            image_paths = [image_paths]
        if image_paths is None:
            raw_paths = filedialog.askopenfilenames(
                filetypes=[("图片文件", "*" + ";*".join(Setting.accepted_exts))]
            )
            if not raw_paths:
                return
            image_paths = list(raw_paths)

        if len(image_paths) > 1:
            self._write_queue_file(image_paths)
            self.__search_image()
        else:
            self._delete_queue_file()
            image_path = image_paths[0]
            if not Path(image_path).is_file():
                return
            tab = self.app.view.search_tab
            tab.search_entry.delete(0, tk.END)
            tab.search_entry.insert(0, image_path)
            image_obj = image_ops.parse_image_from_path(image_path)
            if image_obj is None:
                messagebox.showwarning("警告", "无法识别该图片类型！")
                return
            self.__search_image(image_obj)

    @decorators.send_task
    def search_image_by_clipboard(self) -> None:
        image_obj = image_ops.parse_image_from_clipboard_bytes()
        image_path = None

        if image_obj is None:
            try:
                copy_text = self.app.view.clipboard_get()
                all_paths = [Path(l.strip()) for l in copy_text.splitlines() if l.strip()]
                valid_paths = [str(p.absolute()) for p in all_paths if p.is_file()]
                if len(valid_paths) > 1:
                    self._write_queue_file(valid_paths)
                    self.__search_image()
                    return
                elif len(valid_paths) == 1:
                    image_obj = image_ops.parse_image_from_path(valid_paths[0])
                    if image_obj is not None:
                        image_path = Path(valid_paths[0])
                    else:
                        raise tk.TclError
                else:
                    image_obj = image_ops.parse_image_from_url(copy_text)
                    if image_obj is None:
                        raise tk.TclError
            except tk.TclError:
                messagebox.showinfo("提示", "无法识别剪切板中的图片数据！")
                return
        if image_path is None:
            image_path = file_ops.generate_unique_filename(Setting.temp_image_path, ".jpg")
            if file_ops.get_folder_size(Setting.temp_image_path) > 1024 * 1024 * 30:
                file_ops.clear_folder_all(Setting.temp_image_path)
            if not image_path.parent.exists():
                Setting.temp_image_path.mkdir(exist_ok=True)
            image_obj.save(image_path)

        tab = self.app.view.search_tab
        tab.search_entry.delete(0, tk.END)
        tab.search_entry.insert(0, str(image_path.absolute()))
        self._delete_queue_file()
        self.__search_image(image_obj)

    @decorators.send_task
    def search_image_by_text(self) -> None:
        text = self.app.view.search_tab.search_entry.get().strip()
        self._delete_queue_file()
        self.__search_image(text)

    def __search_image(self, input_data: Image.Image | str | None = None) -> None:
        assert self.app.search_tools
        if not self.app.setting.model.search_dir:
            messagebox.showinfo("提示", "请在设置选项卡索引至少一个目录！")
            return
        if not self._is_finish_search:
            return
        self._is_finish_search = False
        try:
            tab = self.app.view.search_tab

            if input_data is None and self._queue_total > 0:
                tab.set_nav_state(
                    has_prev=self._queue_index > 0,
                    has_next=self._queue_index < self._queue_total - 1
                )
                tab.set_nav_page_label(self._queue_index + 1, self._queue_total)
                queue_path = linecache.getline(str(Setting.temp_multi_search_queue), self._queue_index + 1).strip()
                if not queue_path or not Path(queue_path).is_file():
                    messagebox.showinfo("提示", f"第 {self._queue_index + 1} 张图片不存在或已被删除！")
                    return
                tab.search_entry.delete(0, tk.END)
                tab.search_entry.insert(0, queue_path)
                image_obj = image_ops.parse_image_from_path(queue_path)
                if image_obj is None:
                    messagebox.showwarning("警告", "无法识别该图片类型！")
                    return
                tab.preview_canvas1.append_result(queue_path, image_obj)
                tab.set_nav_visible(True)
                actual_input = image_obj
            else:
                if self._queue_total == 0:
                    tab.set_nav_visible(False)
                if isinstance(input_data, str):
                    tab.preview_canvas1.clear_results()
                    actual_input = input_data
                elif isinstance(input_data, Image.Image):
                    source_path = tab.search_entry.get().strip()
                    if source_path and Path(source_path).is_file():
                        tab.preview_canvas1.append_result(source_path, input_data)
                    actual_input = input_data
                else:
                    return

            self._last_search_content = actual_input
            tab.preview_view.clear_results()
            ext, size_min, size_max, folder_filters = self.app.filter_controller.get_search_filters()
            results = self.app.search_tools.checkout(
                actual_input, self.similarity_threshold,
                ext, size_min, size_max, folder_filters
            )
            try:
                first_result = next(results)
            except StopIteration:
                status = self.app.search_tools.checkout_status
                if status == SearchStatus.EMPTY_INDEX:
                    messagebox.showinfo("提示", "索引中还没有任何图像，也许\n你还没有添加并更新索引目录？")
                elif status == SearchStatus.EMPTY_INPUT:
                    messagebox.showinfo("提示", "输入内容为空，没有搜索结果哦！")
                elif status == SearchStatus.NO_RESULTS:
                    messagebox.showinfo("提示", "筛选条件过于严格，没有匹配到任何图像！")
                else:
                    messagebox.showerror("错误", "图片搜索失败！\n请查看config/error.log获取错误信息！")
                return
            first_img_path, first_sim = first_result
            if Path(first_img_path).exists():
                first_extra_info = SearchController.generate_extra_info(first_img_path, first_sim)
                item = tab.preview_view.append_result(first_img_path, *first_extra_info)
                tab.preview_view.selection_set(item)

            for img_path, similarity in results:
                if Path(img_path).exists():
                    extra_info = SearchController.generate_extra_info(img_path, similarity)
                    tab.preview_view.append_result(img_path, *extra_info)
        except Exception as e:
            logging.error(f"搜索异常: {e}", exc_info=True)
            messagebox.showerror("搜索失败", f"搜索过程发生异常：{e}\n请查看 error.log 获取详细信息。")
        finally:
            self._is_finish_search = True

    def _write_queue_file(self, paths: list[str]) -> None:
        linecache.clearcache()
        Setting.temp_multi_search_queue.parent.mkdir(parents=True, exist_ok=True)
        Setting.temp_multi_search_queue.write_text("\n".join(paths), encoding="utf-8")
        self._queue_index = 0
        self._queue_total = len(paths)

    def _delete_queue_file(self) -> None:
        if Setting.temp_multi_search_queue.exists():
            Setting.temp_multi_search_queue.unlink(missing_ok=True)
        self._queue_index = self._queue_total = 0

    def _debounce_navigate(self, direction: int) -> None:
        def do_navigate() -> None:
            self._nav_debounce_timer = None
            if 0 <= self._queue_index < self._queue_total:
                self.__search_image()
        tab = self.app.view.search_tab
        self._queue_index = max(0, min(self._queue_index + direction, self._queue_total - 1))
        if self._nav_debounce_timer is not None:
            tab.after_cancel(self._nav_debounce_timer)
        self._nav_debounce_timer = tab.after(50, do_navigate)

    @staticmethod
    def generate_extra_info(image_path: str, similarity: float) -> tuple:
        image_path_obj = Path(image_path)
        mtime = datetime.datetime.fromtimestamp(os.path.getmtime(image_path))
        content = (
            f"{os.path.getsize(image_path_obj) / 1024 / 1024:.2f}MB",
            mtime.strftime("%Y-%m-%d %H:%M:%S"),
            f"{similarity:.2f}%"
        )
        return content

    def resend_last_search(self) -> None:
        if self._last_search_content:
            self.__search_image(self._last_search_content)

    def set_preview_result_count(self, max_match_count: int) -> None:
        assert self.app.search_tools
        self.app.setting.app.max_match_count = min(max_match_count, 100)
        self.app.search_tools.update_max_match_count(max_match_count)
        self.resend_last_search()

    def set_similarity_threshold(self, value: float | None) -> None:
        try:
            if value is not None:
                self.similarity_threshold = min(float(value), 100)
        except (ValueError, TypeError):
            self.similarity_threshold = 0.0

    def set_preview_mode(self, mode: Literal["medium_ico", "detail_info"]) -> None:
        tab = self.app.view.search_tab
        results = tab.preview_view.get_show_results()
        current_selection = tab.preview_view.selection()
        tab.preview_view.destroy()
        self.app.setting.app.preview_mode = mode
        if mode == "detail_info":
            tab.preview_view = DetailListView(
                tab.preview_container,
                {"大小": 100, "修改时间": 160, "相似度": 100}
            )
        else:
            tab.preview_view = ThumbnailGridView(tab.preview_container)
        if self._queue_total > 0:
            tab.set_nav_visible(True)
        self.app.bind_event()
        for result in results:
            img_path, *extra_info = result
            tab.preview_view.append_result(img_path, *extra_info)
        tab.preview_view.selection_set(*current_selection)

    def preview_found_image(self, event: tk.Event) -> None:
        @decorators.send_task
        def _preview() -> None:
            try:
                first_item = selection[0]
                image_path = self.app.view.search_tab.preview_view.item(first_item)[0]
                image_obj = image_ops.parse_image_from_path(image_path)
                if image_obj is not None:
                    self.app.view.search_tab.preview_canvas2.append_result(image_path, image_obj)
            except KeyError:
                return
        selection = self.app.view.search_tab.preview_view.selection()
        if not selection:
            return
        if self._preview_timer is not None:
            self.app.view.after_cancel(self._preview_timer)
        self._preview_timer = self.app.view.after(100, _preview)
