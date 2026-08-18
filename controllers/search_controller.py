from __future__ import annotations

from pathlib import Path
from tkinter import filedialog, messagebox
from typing import TYPE_CHECKING, Literal
from dataclasses import dataclass
from threading import Event
import tkinter as tk
import datetime
import logging
import math

from PIL import Image

from core import SearchStatus
from config.settings import Setting, TkS
from utils.i18n import _
from views.widgets import DetailListView, ThumbnailGridView
import utils.shortcut as shortcut
import utils.decorators as decorators
import utils.file_ops as file_ops
import utils.image_ops as image_ops

if TYPE_CHECKING:
    from .app_controller import AppController


class SearchController:
    def __init__(self, app_controller: AppController) -> None:
        self.app = app_controller
        self.__last_search_content: Path | str = ""
        self.__last_save_dir: Path | None = None
        self.__is_finish_search: Event = Event()
        self.__current_page: int = 0
        self.__queue_paths: list[str] = []
        self.__preview_timer: str | None = None
        self.__nav_debounce_timer: str | None = None
        self.__show_toast_timer: str | None = None

    def env_init(self, only_preview_widgets: bool = False) -> None:
        tab = self.app.view.search_tab
        inner_shortcut = (
            (["Ctrl", "A"], lambda _: tab.preview_view.selection_set(tk.ALL)),
            (["Ctrl", "V"], lambda _: self.search_image_by_clipboard()),
            (["Ctrl", "←"], lambda _: self.__debounce_navigate(-1)),
            (["Ctrl", "→"], lambda _: self.__debounce_navigate(1)),
        )
        self.__is_finish_search.set()
        if only_preview_widgets:
            for w in (tab.preview_canvas1, tab.preview_canvas2, tab.preview_view):
                w.bind("<Button-3>", self.app.menu_controller.show_context_menu)
                w.bind("<Double-Button-1>", self.app.menu_controller.double_click_open_file)
            tab.preview_view.bind("<<ItemviewSelect>>", lambda _: self.__preview_found_image())
            tab.preview_view.bind("<FocusIn>", lambda _: shortcut.reset_modifiers(), add="+")
            tab.preview_view.bind("<KeyPress>", shortcut.track_modifiers, add="+")
            tab.preview_view.bind("<KeyRelease>", shortcut.track_modifiers, add="+")
            tab.preview_view.bind("<KeyPress>", self.app.menu_controller.on_menu_shortcut, add="+")
            tab.preview_view.bind("<KeyPress>", lambda e: self.app.setting_controller.on_inner_shortcut(e, inner_shortcut), add="+")
            return
        tab = self.app.view.search_tab
        tab.search_by_browser_btn.config(command=self.search_by_browser)
        tab.search_by_clipboard_btn.config(command=self.search_image_by_clipboard)
        tab.nav_prev.config(command=lambda: self.__debounce_navigate(-1))
        tab.nav_next.config(command=lambda: self.__debounce_navigate(1))
        tab.filter_panel.confirm_btn.config(command=self.app.filter_controller.confirm_filter)
        tab.filter_panel.cancel_btn.config(command=self.app.filter_controller.cancel_filter)
        tab.more_options_button.bind("<ButtonPress-1>", lambda e: (self.app.menu_controller.show_adjustment_menu(e), "break")[1])
        tab.filter_btn.bind("<Button-1>", lambda e: self.app.filter_controller.toggle_filter_panel())
        tab.search_entry.bind("<Return>", lambda e: self.search_image_by_text())   

    @decorators.send_task
    def search_by_browser(self, image_paths: list[str] | None = None) -> None:
        if image_paths is None:
            raw_paths = filedialog.askopenfilenames(
                filetypes=[(_("图片文件"), "*" + ";*".join(Setting.accepted_exts))],
                initialdir=self.__last_save_dir
            )
            if not raw_paths:
                return
            image_paths = list(raw_paths)
            self.__last_save_dir = Path(image_paths[0]).parent

        if len(image_paths) > 1:
            self.__queue_paths = image_paths
            self.__current_page = 0
            self.__search_image()
        else:
            self.__queue_paths = []
            self.__current_page = 0
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
            except tk.TclError:
                messagebox.showinfo(_("提示"), _("无法识别剪切板中的图片数据！"))
                return
            lines = copy_text.splitlines()
            if len(lines) > 3000:
                lines = lines[:3000]
                self.show_toast(_("内容过长，已截断到3000行。"))
            accept_exts = set(Setting.accepted_exts)
            all_paths = [Path(l.strip()) for l in lines if l.strip()]
            valid_paths = [str(p.absolute()) for p in all_paths if p.is_file() and p.suffix.lower() in accept_exts]
            if len(valid_paths) > 1:
                self.__queue_paths = valid_paths
                self.__current_page = 0
                self.__search_image()
                return
            if len(valid_paths) == 1:
                image_obj = image_ops.parse_image_from_path(valid_paths[0])
            if image_obj is None:
                image_obj = image_ops.parse_image_from_url(copy_text)
                if image_obj is None:
                    messagebox.showinfo(_("提示"), _("无法识别剪切板中的图片数据！"))
                    return
            else:
                image_path = Path(valid_paths[0])
        if image_path is None:
            image_path = file_ops.generate_unique_filename(Setting.temp_image_path, ".jpg")
            if file_ops.get_folder_size(Setting.temp_image_path) > 1024 * 1024 * 30:
                file_ops.rmtree(Setting.temp_image_path)
            if not image_path.parent.exists():
                Setting.temp_image_path.mkdir(exist_ok=True)
            image_obj.save(image_path)

        self.__queue_paths = []
        self.__current_page = 0
        self.__search_image(image_obj, source_path=str(image_path.absolute()))

    @decorators.send_task
    def search_image_by_text(self) -> None:
        text = self.app.view.search_tab.search_entry.get().strip()
        self.__queue_paths = []
        self.__current_page = 0
        self.__search_image(text)

    def resend_last_search(self) -> None:
        if isinstance(self.__last_search_content, str):
            if self.__last_search_content != "":
                self.__search_image(self.__last_search_content)
        elif len(self.__queue_paths) > 0:
            self.__search_image()
        else:
            self.search_by_browser([str(self.__last_search_content)])

    def set_preview_result_count(self, max_match_count: int) -> None:
        assert self.app.search_tools
        try:
            self.app.setting.app.max_match_count = max(min(max_match_count, 500), 1)
            self.app.search_tools.update_max_match_count(self.app.setting.app.max_match_count)
            self.resend_last_search()
        except TypeError:
            return

    def set_preview_mode(self, mode: Literal["detail_info", "medium_ico", "big_ico", "huge_ico"]) -> None:
        tab = self.app.view.search_tab
        results = tab.preview_view.get_show_results()
        current_selection = tab.preview_view.selection()
        self.app.setting.app.preview_mode = mode
        if mode == "detail_info":
            if isinstance(tab.preview_view, DetailListView):
                return
            tab.preview_view.destroy()
            tab.preview_view = DetailListView(tab.preview_container, {_("大小"): 100, _("修改时间"): 160, _("相似度"): 100})
            self.env_init(only_preview_widgets=True)
        else:
            thumbnail_size = {"medium_ico": 110, "big_ico": 150, "huge_ico": 230}.get(mode, 110)
            tab.preview_view.destroy()
            tab.preview_view = ThumbnailGridView(tab.preview_container, thumbnail_size)
            self.env_init(only_preview_widgets=True)
        if len(self.__queue_paths) > 0:
            tab.set_nav_visible(True)
        self.__smooth_preview(iter(results), B_min=50, B_max=300, r=10, m=1)
        tab.preview_view.selection_set(*current_selection)

    def show_toast(self, message: str, duration: int = 1500) -> None:
        toast = self.app.view.search_tab.toast_label
        toast.config(text=message)
        toast.place(in_=self.app.view.search_tab.preview_view, relx=1.0, rely=1.0, anchor=tk.SE, height=TkS(30))   # type: ignore
        toast.lift()
        if self.__show_toast_timer is not None:
            self.app.view.after_cancel(self.__show_toast_timer)
        self.__show_toast_timer = self.app.view.after(duration, lambda: toast.place_forget())

    @staticmethod
    def __generate_extra_info(image_path: Path, similarity: float) -> tuple:
        st = image_path.stat()
        mtime = datetime.datetime.fromtimestamp(st.st_mtime)
        content = (
            f"{st.st_size / 1024 / 1024:.2f}MB",
            mtime.strftime("%Y-%m-%d %H:%M:%S"),
            f"{similarity:.2f}%"
        )
        return content

    def __search_image(self, input_data: Image.Image | str | None = None, source_path: str | None = None) -> None:
        assert self.app.search_tools
        if not self.__is_allow_to_search():
            return
        self.__is_finish_search.clear()
        tab = self.app.view.search_tab
        if len(self.__queue_paths) > 0 or input_data is None:
            tab.set_nav_state(self.__current_page > 0, self.__current_page < len(self.__queue_paths) - 1)
            tab.set_nav_page_label(self.__current_page + 1, len(self.__queue_paths))
            source_path = self.__queue_paths[self.__current_page]
            if not source_path or not Path(source_path).is_file():
                tab.preview_view.clear()
                self.show_toast(_("第 {n} 张图片不存在或已被删除！", n=self.__current_page + 1))
                self.__is_finish_search.set()
                return
            input_data = image_ops.parse_image_from_path(source_path)
            if input_data is None:
                messagebox.showwarning(_("警告"), _("无法识别该图片类型！"))
                self.__is_finish_search.set()
                return
            tab.set_nav_visible(True)
        else:
            tab.set_nav_visible(False)

        if not self.__setup_search_ui(input_data, source_path):
            return
        try:
            tab.preview_view.clear()
            threshold, ext, size_min, size_max, folder_filters, dedup = self.app.filter_controller.get_search_filters()
            results = self.app.search_tools.checkout(input_data, threshold, ext, size_min, size_max, folder_filters, dedup)
            try:
                first_result = next(results)
            except StopIteration:
                self.__handle_empty_result(self.app.search_tools.checkout_status)
                self.__is_finish_search.set()
                return
            first_img_path, first_sim = first_result
            first_extra_info = self.__generate_extra_info(first_img_path, first_sim)
            item = tab.preview_view.append(first_img_path, *first_extra_info)
            tab.preview_view.selection_set(item)
            self.__smooth_preview(((img_path, *self.__generate_extra_info(img_path, sim)) for img_path, sim in results))
            if self.app.search_tools.checkout_status == SearchStatus.PARTIAL_OMITTED:
                self.show_toast(_("部分无效结果被隐藏，建议更新索引。"), duration=3000)
        except Exception as e:
            logging.error(f"搜索异常: {e}", exc_info=True)
            messagebox.showerror(_("错误"), _("搜索过程发生异常：{e}", e=str(e)))
            self.__is_finish_search.set()

    def __is_allow_to_search(self) -> bool:
        assert self.app.search_tools
        if not self.app.setting.model.index.search_dir:
            messagebox.showinfo(_("提示"), _("请在索引选项卡索引至少一个目录！"))
            return False
        if not self.__is_finish_search.is_set():
            return False
        if self.app.index_controller.is_updating:
            if self.app.index_controller.is_auto_updating:
                self.app.search_tools.force_stop_update = True
            else:
                if not messagebox.askyesno(_("提示"), _("索引正在更新中，是否终止索引更新？")):
                    return False
                if self.app.index_controller.is_updating:
                    self.app.search_tools.force_stop_update = True
        return True

    def __setup_search_ui(self, input_data: Image.Image | str | None, source_path: str | None) -> bool:
        tab = self.app.view.search_tab
        if isinstance(input_data, str):
            tab.preview_canvas1.clear()
            self.__last_search_content = input_data
        elif isinstance(input_data, Image.Image):
            tab.search_entry.delete(0, tk.END)
            tab.search_entry.insert(0, str(Path(source_path).resolve()) if source_path else "")
            tab.search_entry.xview_moveto(1.0)
            source_path_obj = Path(source_path) if source_path is not None else "" 
            if source_path_obj and source_path_obj.is_file():
                tab.preview_canvas1.append(source_path_obj, input_data)
            self.__last_search_content = source_path_obj
        else:
            return False
        return True

    def __handle_empty_result(self, status: SearchStatus) -> None:
        if status == SearchStatus.EMPTY_INDEX:
            messagebox.showinfo(_("提示"), _("索引中还没有任何图像，也许\n你还没有点击更新索引目录？"))
        elif status == SearchStatus.EMPTY_INPUT:
            messagebox.showinfo(_("提示"), _("请输入搜索内容！"))
        elif status == SearchStatus.NO_RESULTS:
            messagebox.showinfo(_("提示"), _("筛选条件过于严格，没有匹配到任何图像！"))
        elif status == SearchStatus.ENCODE_FAILED:
            messagebox.showerror(_("错误"), _("图片搜索失败！\n请查看config/data/error.log获取错误信息！"))

    def __smooth_preview(self, results_iter, B_min=10, B_max=100, r=0.8, m=5) -> None:
        preview_batch_k = 0
        preview_batch_buffer = []
        preview_iter = results_iter

        def process_next_batch() -> None:
            nonlocal preview_batch_k, preview_batch_buffer, preview_iter
            if preview_iter is None:
                return
            batch_size = max(1, round(B_min + (B_max - B_min) / (1 + math.exp(-r * (preview_batch_k - m)))))
            buffer = preview_batch_buffer
            try:
                while len(buffer) < batch_size:
                    img_path, *extra_info = next(preview_iter)
                    if img_path.exists():
                        buffer.append((img_path, *extra_info))
            except StopIteration:
                if buffer:
                    self.__append_preview_results(buffer)
                preview_iter = None
                preview_batch_buffer = []
                self.__is_finish_search.set()
                return
            self.__append_preview_results(buffer)
            preview_batch_k += 1
            preview_batch_buffer = []
            self.app.view.after(10, process_next_batch)
        
        return process_next_batch()

    def __append_preview_results(self, results) -> None:
        try:
            for res in results:
                self.app.view.search_tab.preview_view.append(*res)
        except Exception as e:
            logging.error(f"插入搜索结果时出现异常：{e}")
            self.__is_finish_search.set()
            raise RuntimeError("强制终止搜索")

    def __debounce_navigate(self, direction: int) -> None:
        @decorators.send_task
        def wait_to_finish_search():
            self.__is_finish_search.wait()
            if 0 <= self.__current_page < len(self.__queue_paths):
                self.__search_image()
        
        def do_navigate() -> None:
            self.__nav_debounce_timer = None
            wait_to_finish_search()
            
        tab = self.app.view.search_tab
        new_page = self.__current_page + direction
        if new_page < 0 or new_page > len(self.__queue_paths) - 1:
            return
        self.__current_page = new_page
        tab.set_nav_state(self.__current_page > 0, self.__current_page < len(self.__queue_paths) - 1)
        tab.set_nav_page_label(self.__current_page + 1, len(self.__queue_paths))
        if self.__nav_debounce_timer is not None:
            tab.after_cancel(self.__nav_debounce_timer)
        self.__nav_debounce_timer = tab.after(200, do_navigate)

    def __preview_found_image(self) -> None:
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



@dataclass(slots=True)
class FilterSnapshot:
    threshold: float = 0.0
    ext: str = ""
    size_min: str = ""
    size_min_unit: str = ""
    size_max: str = ""
    size_max_unit: str = ""
    folder_selection: tuple = ()
    folder_all: bool = True
    dedup: bool = False


class FilterController:
    def __init__(self, app_controller: AppController) -> None:
        self.app = app_controller
        self._folder_paths: list[str] = []
        self._saved_state: FilterSnapshot | None = None

    def env_init(self) -> None:
        fp = self.app.view.search_tab.filter_panel
        for i in range(2):
            fp.dedup_check.invoke()
        fp.folder_select_all.config(
            command=lambda: fp.folder_listbox.select_set(0, tk.END) 
            if fp.folder_select_all.instate(["selected"]) else fp.folder_listbox.selection_clear(0, tk.END)
        )
        fp.sim_scale.config(command=lambda value: (fp.sim_value.config(text=f"{int(float(value))}%")))
        fp.folder_listbox.bind("<<ListboxSelect>>", lambda _: fp.folder_select_all.state(
            ['selected'] if len(fp.folder_listbox.curselection()) == fp.folder_listbox.size() else ['!selected']
        ))
        self.refresh_folder_filter()
        fp.folder_select_all.invoke()

    def refresh_folder_filter(self) -> None:
        dirs = self.app.setting.model.index.search_dir
        self._folder_paths = dirs
        fp = self.app.view.search_tab.filter_panel
        lb = fp.folder_listbox
        lb.delete(0, tk.END)
        for d in self._folder_paths:
            lb.insert(tk.END, d)
        if fp.folder_select_all.instate(["selected"]):
            lb.selection_set(0, tk.END)

    def get_search_filters(self) -> tuple:
        def parse_size(text: str, unit: str) -> float | None:
            t = text.strip()
            try:
                value = float(t) if t else None
            except ValueError:
                return None
            if value is None:
                return None
            return value / 1024 if unit == "KB" else value

        fp = self.app.view.search_tab.filter_panel
        threshold = fp.sim_scale.get()
        ext = fp.ext_combo.get()
        size_min = parse_size(fp.size_min.get(), fp.size_min_unit.get())
        size_max = parse_size(fp.size_max.get(), fp.size_max_unit.get())
        if fp.folder_select_all.instate(["selected"]):
            folder_filters = None
        else:
            selected = fp.folder_listbox.curselection()
            folder_filters = [self._folder_paths[i] for i in selected] or None
        dedup = fp.dedup_check.instate(['selected'])
        return threshold, ext, size_min, size_max, folder_filters, dedup

    def toggle_filter_panel(self) -> None:
        fp = self.app.view.search_tab.filter_panel
        if fp.winfo_viewable():
            fp.place_forget()
        else:
            self._saved_state = FilterSnapshot(
                threshold=fp.sim_scale.get(),
                ext=fp.ext_combo.get(),
                size_min=fp.size_min.get(),
                size_min_unit=fp.size_min_unit.get(),
                size_max=fp.size_max.get(),
                size_max_unit=fp.size_max_unit.get(),
                folder_selection=fp.folder_listbox.curselection(),
                folder_all=fp.folder_select_all.instate(["selected"]),
                dedup=fp.dedup_check.instate(['selected']),
            )
            fp.update_idletasks()
            fp.place(relx=0.005, rely=0.094, relwidth=0.4, height=fp.winfo_reqheight())
            fp.lift()

    def confirm_filter(self) -> None:
        self.app.view.search_tab.filter_panel.place_forget()
        self.app.search_controller.resend_last_search()

    def cancel_filter(self) -> None:
        s = self._saved_state
        if s is None:
            return
        fp = self.app.view.search_tab.filter_panel
        fp.sim_scale.set(s.threshold)
        fp.sim_value.config(text=f"{int(s.threshold)}%")
        fp.ext_combo.set(s.ext)
        fp.size_min.delete(0, tk.END)
        fp.size_min.insert(0, s.size_min)
        fp.size_min_unit.set(s.size_min_unit)
        fp.size_max.delete(0, tk.END)
        fp.size_max.insert(0, s.size_max)
        fp.size_max_unit.set(s.size_max_unit)
        fp.folder_listbox.selection_clear(0, tk.END)
        for idx in s.folder_selection:
            fp.folder_listbox.selection_set(idx)
        fp.folder_select_all.state(['selected'] if s.folder_all else ['!selected'])
        if s.dedup != fp.dedup_check.instate(['selected']):
            fp.dedup_check.invoke()
        self.app.view.search_tab.filter_panel.place_forget()

    def on_root_click(self, event) -> None:
        fp = self.app.view.search_tab.filter_panel
        if not fp.winfo_viewable():
            return
        w = event.widget
        if w == self.app.view.search_tab.filter_btn:
            return
        while w:
            if w == fp or isinstance(w, str):
                return
            w = w.master
        self.cancel_filter()
