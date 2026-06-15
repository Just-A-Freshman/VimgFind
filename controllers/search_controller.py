from __future__ import annotations

from tkinter import filedialog, messagebox
from typing import TYPE_CHECKING, Literal
from pathlib import Path
import datetime
import os
import tkinter as tk

from PIL import Image

from setting import Setting
from utils import ImageOperation, FileOperation, Decorator
from search_tools import SearchStatus

if TYPE_CHECKING:
    from .app_controller import AppController


class SearchController(object):
    def __init__(self, app_controller: AppController) -> None:
        self._last_search_content: Image.Image | str = ""
        self._is_finish_search: bool = True
        self._preview_timer = ""
        self.similarity_threshold: float = 0.0
        self.app = app_controller

    @Decorator.send_task
    def search_by_browser(self, image_path: str | None = None) -> None:
        if image_path is not None and not Path(image_path).is_file():
            return
        if not image_path:
            image_path = filedialog.askopenfilename(
                filetypes=[("图片文件", "*" + ";*".join(Setting.accepted_exts))]
            )
            if not image_path:
                return
        tab = self.app.view.search_tab
        tab.search_entry.delete(0, tk.END)
        tab.search_entry.insert(0, image_path)
        image_obj = ImageOperation.parse_image_from_path(image_path)
        if image_obj is None:
            messagebox.showwarning("警告", "无法识别该图片类型！")
            return
        tab.preview_canvas1.append_result(image_path, image_obj)
        self.__search_image(image_obj)

    @Decorator.send_task
    def search_image_by_clipboard(self) -> None:
        image_obj = ImageOperation.parse_image_from_clipboard_bytes()
        image_path = None

        if image_obj is None:
            try:
                copy_text = self.app.view.clipboard_get()
                image_obj = ImageOperation.parse_image_from_path(copy_text)
                if image_obj is not None:
                    image_path = Path(copy_text)
                else:
                    image_obj = ImageOperation.parse_image_from_url(copy_text)
                    if image_obj is None:
                        raise tk.TclError
            except tk.TclError:
                messagebox.showinfo("提示", "无法识别剪切板中的图片数据！")
                return
        if image_path is None:
            image_path = FileOperation.generate_unique_filename(Setting.temp_image_path, ".jpg")
            if os.path.getsize(Setting.temp_image_path) > 1024 * 1024 * 30:
                FileOperation.clear_folder_all(Setting.temp_image_path)
            if not image_path.parent.exists():
                Path.mkdir(Setting.temp_image_path, exist_ok=True)
            image_obj.save(image_path)

        tab = self.app.view.search_tab
        tab.preview_canvas1.append_result(str(image_path.absolute()), image_obj)
        self.__search_image(image_obj)

    @Decorator.send_task
    def search_image_by_text(self) -> None:
        text = self.app.view.search_tab.search_entry.get().strip()
        self.app.view.search_tab.preview_canvas1.clear_results()
        self.__search_image(text)

    def __search_image(self, input_data: Image.Image | str) -> None:
        if not self.app.setting.get_config("index", "search_dir"):
            messagebox.showinfo("提示", "请在设置选项卡索引至少一个目录！")
            return
        if not self._is_finish_search:
            return
        self._is_finish_search = False
        self._last_search_content = input_data
        self.app.view.search_tab.preview_view.clear_results()

        ext, size_min, size_max, folder_filters = self.app.filter_controller.get_search_filters()
        results = self.app.search_tools.checkout(
            input_data, self.similarity_threshold,
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
            self._is_finish_search = True
            return
        first_img_path, first_sim = first_result
        tab = self.app.view.search_tab
        if Path(first_img_path).exists():
            first_extra_info = SearchController.generate_extra_info(first_img_path, first_sim)
            item = tab.preview_view.append_result(first_img_path, *first_extra_info)
            tab.preview_view.selection_set(item)

        for img_path, similarity in results:
            if Path(img_path).exists():
                extra_info = SearchController.generate_extra_info(img_path, similarity)
                tab.preview_view.append_result(img_path, *extra_info)
        self._is_finish_search = True

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

    def set_preview_result_count(self, max_match_count: int) -> None:
        self.app.setting.modity_config("index", "max_match_count", min(max_match_count, 100))
        self.app.search_tools.update_max_match_count(max_match_count)
        if self._last_search_content:
            self.__search_image(self._last_search_content)

    def set_similarity_threshold(self, value: float) -> None:
        try:
            self.similarity_threshold = min(float(value), 100)
        except (ValueError, TypeError):
            self.similarity_threshold = 0.0

    def resend_last_search(self) -> None:
        if self._last_search_content:
            self.__search_image(self._last_search_content)

    def set_preview_mode(self, mode: Literal["detail_info", "medium_ico"]) -> None:
        tab = self.app.view.search_tab
        results = tab.preview_view.get_show_results()
        current_selection = tab.preview_view.selection()
        tab.preview_view.destroy()
        self.app.setting.modity_config("function", "preview_mode", mode)

        from widgets import DetailListView, ThumbnailGridView
        if mode == "detail_info":
            tab.preview_view = DetailListView(
                tab.preview_container,
                {"大小": 100, "修改时间": 160, "相似度": 100}
            )
        else:
            tab.preview_view = ThumbnailGridView(tab.preview_container)

        self.app.bind_event()
        for result in results:
            img_path, *extra_info = result
            tab.preview_view.append_result(img_path, *extra_info)
        tab.preview_view.selection_set(*current_selection)

    def preview_found_image(self, event: tk.Event) -> None:
        @Decorator.send_task
        def _preview() -> None:
            try:
                first_item = selection[0]
                image_path = self.app.view.search_tab.preview_view.item(first_item)[0]
                image_obj = ImageOperation.parse_image_from_path(image_path)
                if image_obj is not None:
                    self.app.view.search_tab.preview_canvas2.append_result(image_path, image_obj)
            except KeyError:
                return
        selection = self.app.view.search_tab.preview_view.selection()
        if not selection:
            return
        if self._preview_timer:
            self.app.view.after_cancel(self._preview_timer)
        self._preview_timer = self.app.view.after(100, _preview)
