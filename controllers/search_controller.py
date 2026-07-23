from __future__ import annotations

from pathlib import Path
from tkinter import filedialog, messagebox
from typing import TYPE_CHECKING, Literal
import datetime
import linecache
import logging
import os
import tkinter as tk

from core import SearchStatus
from PIL import Image

from config.settings import Setting
from utils.i18n import _
from views.widgets import DetailListView, ThumbnailGridView
import utils.decorators as decorators
import utils.file_ops as file_ops
import utils.image_ops as image_ops

if TYPE_CHECKING:
    from .app_controller import AppController


class SearchController:
    def __init__(self, app_controller: AppController) -> None:
        self.app = app_controller
        self.similarity_threshold: float = 0.0
        self.__last_search_content: Path | str = ""
        self.__is_finish_search: bool = True
        self.__preview_timer: str | None = None
        self.__queue_index: int = 0
        self.__queue_total: int = 0
        self.__nav_debounce_timer: str | None = None

    def env_init(self, only_preview_widget: bool = False) -> None:
        tab = self.app.view.search_tab
        if only_preview_widget:
            for w in (tab.preview_canvas1, tab.preview_canvas2, tab.preview_view):
                w.bind("<Button-3>", lambda e, w=w: self.app.menu_controller.show_selected_image_menu(e, w))
                w.bind("<Double-Button-1>", lambda e, w=w: self.app.menu_controller.double_click_open_file(e, w))
            tab.preview_view.bind("<<ItemviewSelect>>", self.__preview_found_image)
            tab.preview_view.bind("<Control-a>", lambda e: tab.preview_view.selection_set(tk.ALL))
            tab.preview_view.bind("<Control-v>", lambda e: self.search_image_by_clipboard())
            return
        tab.search_by_browser_btn.config(command=self.search_by_browser)
        tab.search_by_clipboard_btn.config(command=self.search_image_by_clipboard)
        tab.nav_prev.config(command=lambda: self.__debounce_navigate(-1))
        tab.nav_next.config(command=lambda: self.__debounce_navigate(1))
        tab.more_options_button.config(command=lambda: self.app.menu_controller.show_adjustment_menu(tab.more_options_button))
        tab.filter_panel.confirm_btn.config(command=self.app.filter_controller.confirm_filter)
        tab.filter_panel.cancel_btn.config(command=self.app.filter_controller.cancel_filter)
        tab.filter_btn.bind("<Button-1>", lambda e: self.app.filter_controller.toggle_filter_panel())
        tab.search_entry.bind("<Return>", lambda e: self.search_image_by_text())

    @decorators.send_task
    def search_by_browser(self, image_paths: list[str] | None = None) -> None:
        if image_paths is None:
            raw_paths = filedialog.askopenfilenames(filetypes=[(_("图片文件"), "*" + ";*".join(Setting.accepted_exts))])
            if not raw_paths:
                return
            image_paths = list(raw_paths)

        if len(image_paths) > 1:
            self.__write_queue_file(image_paths)
            self.__search_image()
        else:
            self.__delete_queue_file()
            image_path = image_paths[0]
            if not Path(image_path).is_file():
                return
            image_obj = image_ops.parse_image_from_path(image_path)
            if image_obj is None:
                messagebox.showwarning(_("警告"), _("无法识别该图片类型！"))
                return
            self.__search_image(image_obj, source_path=image_path)

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
                    self.__write_queue_file(valid_paths)
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
                messagebox.showinfo(_("提示"), _("无法识别剪切板中的图片数据！"))
                return
        if image_path is None:
            image_path = file_ops.generate_unique_filename(Setting.temp_image_path, ".jpg")
            if file_ops.get_folder_size(Setting.temp_image_path) > 1024 * 1024 * 30:
                file_ops.rmtree(Setting.temp_image_path)
            if not image_path.parent.exists():
                Setting.temp_image_path.mkdir(exist_ok=True)
            image_obj.save(image_path)

        self.__delete_queue_file()
        self.__search_image(image_obj, source_path=str(image_path.absolute()))

    @decorators.send_task
    def search_image_by_text(self) -> None:
        text = self.app.view.search_tab.search_entry.get().strip()
        self.__delete_queue_file()
        self.__search_image(text)

    def resend_last_search(self) -> None:
        if isinstance(self.__last_search_content, str):
            self.__search_image(self.__last_search_content)
        elif self.__queue_total > 0:
            self.__search_image()
        else:
            self.search_by_browser([str(self.__last_search_content)])

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

    def set_preview_mode(self, mode: Literal["detail_info", "medium_ico", "big_ico", "huge_ico"]) -> None:
        tab = self.app.view.search_tab
        results = tab.preview_view.get_show_results()
        current_selection = tab.preview_view.selection()
        tab.preview_view.destroy()
        self.app.setting.app.preview_mode = mode
        if mode == "detail_info":
            tab.preview_view = DetailListView(tab.preview_container, {_("大小"): 100, _("修改时间"): 160, _("相似度"): 100})
        else:
            thumbnail_size = {"medium_ico": 110, "big_ico": 150, "huge_ico": 230}.get(mode, 220)
            tab.preview_view = ThumbnailGridView(tab.preview_container, thumbnail_size)
        if self.__queue_total > 0:
            tab.set_nav_visible(True)
        self.env_init(only_preview_widget=True)
        for result in results:
            img_path, *extra_info = result
            tab.preview_view.append(img_path, *extra_info)
        tab.preview_view.selection_set(*current_selection)

    def __search_image(self, input_data: Image.Image | str | None = None, source_path: str | None = None) -> None:
        assert self.app.search_tools
        if not self.app.setting.model.index.search_dir:
            messagebox.showinfo(_("提示"), _("请在索引选项卡索引至少一个目录！"))
            return
        if not self.__is_finish_search:
            return
        if self.app.index_controller.is_updating:
            if self.app.index_controller.is_auto_updating:
                self.app.search_tools.force_stop_update = True
            else:
                if not messagebox.askyesno(_("提示"), _("索引正在更新中，是否终止索引更新？")):
                    return
                if self.app.index_controller.is_updating:
                    self.app.search_tools.force_stop_update = True
        self.__is_finish_search = False
        try:
            tab = self.app.view.search_tab
            if self.__queue_total > 0:
                tab.set_nav_state(self.__queue_index > 0, self.__queue_index < self.__queue_total - 1)
                tab.set_nav_page_label(self.__queue_index + 1, self.__queue_total)
                source_path = linecache.getline(str(Setting.temp_multi_search_queue), self.__queue_index + 1).strip()
                if not source_path or not Path(source_path).is_file():
                    messagebox.showinfo(_("提示"), _("第 {n} 张图片不存在或已被删除！", n=self.__queue_index + 1))
                    return
                input_data = image_ops.parse_image_from_path(source_path)
                if input_data is None:
                    messagebox.showwarning(_("警告"), _("无法识别该图片类型！"))
                    return
                tab.set_nav_visible(True)
            else:
                tab.set_nav_visible(False)
            if isinstance(input_data, str):
                tab.preview_canvas1.clear()
                self.__last_search_content = input_data
            elif isinstance(input_data, Image.Image):
                tab.search_entry.delete(0, tk.END)
                tab.search_entry.insert(0, source_path or "")
                tab.search_entry.xview_moveto(1.0)
                if source_path and Path(source_path).is_file():
                    tab.preview_canvas1.append(source_path, input_data)
                self.__last_search_content = Path(source_path) if source_path is not None else ""
            else:
                return
            tab.preview_view.clear()
            ext, size_min, size_max, folder_filters, dedup = self.app.filter_controller.get_search_filters()
            results = self.app.search_tools.checkout(
                input_data, self.similarity_threshold, ext, size_min, size_max, folder_filters, dedup)
            try:
                first_result = next(results)
            except StopIteration:
                status = self.app.search_tools.checkout_status
                if status == SearchStatus.EMPTY_INDEX:
                    messagebox.showinfo(_("提示"), _("索引中还没有任何图像，也许\n你还没有点击更新索引目录？"))
                elif status == SearchStatus.EMPTY_INPUT:
                    pass
                elif status == SearchStatus.NO_RESULTS:
                    messagebox.showinfo(_("提示"), _("筛选条件过于严格，没有匹配到任何图像！"))
                else:
                    messagebox.showerror(_("错误"), _("图片搜索失败！\n请查看config/data/error.log获取错误信息！"))
                return
            first_img_path, first_sim = first_result
            if Path(first_img_path).exists():
                first_extra_info = SearchController.__generate_extra_info(first_img_path, first_sim)
                item = tab.preview_view.append(first_img_path, *first_extra_info)
                tab.preview_view.selection_set(item)

            for img_path, similarity in results:
                if Path(img_path).exists():
                    extra_info = SearchController.__generate_extra_info(img_path, similarity)
                    tab.preview_view.append(img_path, *extra_info)
        except Exception as e:
            logging.error(f"搜索异常: {e}", exc_info=True)
            messagebox.showerror(_("错误"), _("搜索过程发生异常：{e}", e=str(e)))
        finally:
            self.__is_finish_search = True

    def __write_queue_file(self, paths: list[str]) -> None:
        linecache.clearcache()
        Setting.temp_multi_search_queue.parent.mkdir(parents=True, exist_ok=True)
        Setting.temp_multi_search_queue.write_text("\n".join(paths), encoding="utf-8")
        self.__queue_index = 0
        self.__queue_total = len(paths)

    def __delete_queue_file(self) -> None:
        if Setting.temp_multi_search_queue.exists():
            Setting.temp_multi_search_queue.unlink(missing_ok=True)
        self.__queue_index = self.__queue_total = 0

    def __debounce_navigate(self, direction: int) -> None:
        def do_navigate() -> None:
            self.__nav_debounce_timer = None
            if 0 <= self.__queue_index < self.__queue_total:
                self.__search_image()
        tab = self.app.view.search_tab
        self.__queue_index = max(0, min(self.__queue_index + direction, self.__queue_total - 1))
        if self.__nav_debounce_timer is not None:
            tab.after_cancel(self.__nav_debounce_timer)
        self.__nav_debounce_timer = tab.after(50, do_navigate)

    @staticmethod
    def __generate_extra_info(image_path: str, similarity: float) -> tuple:
        st = os.stat(image_path)
        mtime = datetime.datetime.fromtimestamp(st.st_mtime)
        content = (
            f"{st.st_size / 1024 / 1024:.2f}MB",
            mtime.strftime("%Y-%m-%d %H:%M:%S"),
            f"{similarity:.2f}%"
        )
        return content

    def __preview_found_image(self, event: tk.Event) -> None:
        @decorators.send_task
        def _preview() -> None:
            try:
                first_item = selection[0]
                image_path = self.app.view.search_tab.preview_view.item(first_item)[0]
                image_obj = image_ops.parse_image_from_path(image_path)
                if image_obj is not None:
                    self.app.view.search_tab.preview_canvas2.append(image_path, image_obj)
            except KeyError:
                return
        selection = self.app.view.search_tab.preview_view.selection()
        if not selection:
            return
        if self.__preview_timer is not None:
            self.app.view.after_cancel(self.__preview_timer)
        self.__preview_timer = self.app.view.after(100, _preview)
