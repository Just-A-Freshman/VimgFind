from tkinter import messagebox, filedialog, font as tkfont
from ttkbootstrap import Style, Treeview
from tkinterdnd2 import DND_FILES, TkinterDnD
import tkinter as tk
from pathlib import Path
from typing import Literal
import datetime
import os

from ui import WinGUI
from widgets import BasicImagePreviewView, DetailListView, ThumbnailGridView
from setting import Setting, WinInfo
from utils import FileOperation, ImageOperation, Decorator
from search_tools import SearchTool, SearchStatus
import webbrowser


from PIL import Image



class CoreControl(WinGUI):
    def __init__(self) -> None:
        super().__init__()
        self.setting = Setting()
        self.filter_control = FilterController(self)
        self.__change_theme(setting_theme=True)
        self.search_tools = SearchTool(self.setting)
        self.index_table_control = IndexTableControl(self)
        self.search_control = SearchControl(self)
        self.menu_control = MenuControl(self)
        self.search_control.set_preview_mode(self.setting.get_config("function", "preview_mode"))
        self.__env_init()
        self.bind_event(first_time=True)
        
    def bind_event(self, first_time=False) -> None:
        self.preview_view.bind("<<ItemviewSelect>>", self.search_control.preview_found_image)
        self.preview_view.bind("<Control-a>", lambda e: self.preview_view.selection_set(tk.ALL))
        self.preview_view.bind("<Control-v>", lambda e: self.search_control.search_image_by_clipboard())
        preview_widgets = (self.preview_canvas1, self.preview_canvas2, self.preview_view)
        for w in preview_widgets:
            w.bind("<Button-3>", lambda e, w=w: self.menu_control.create_right_click_menu(e, w))
            w.bind("<Double-Button-1>", lambda e, w=w: self.menu_control.double_click_open_file(e, w))

        if not first_time:
            return

        self.search_by_browser_btn.config(command=self.search_control.search_by_browser)
        self.search_by_clipboard_btn.config(command=self.search_control.search_image_by_clipboard)
        self.search_entry.bind("<Return>", lambda e: self.search_control.search_image_by_text())
        self.more_options_button.config(command=self.menu_control.create_preview_setting_menu)
        self.filter_btn.bind("<Button-1>", lambda e: self.filter_control.toggle_filter_panel())
        self.filter_panel.confirm_btn.config(command=self.filter_control.confirm_filter)
        self.filter_panel.cancel_btn.config(command=self.filter_control.cancel_filter)
        self.bind_all("<Button-1>", self.filter_control.on_root_click, "+")
        self.filter_control.init_filter_panel()

        self.index_dataset_table.bind("<Double-Button-1>", self.menu_control.double_click_open_file)
        self.index_dataset_table.bind("<ButtonPress-1>", self.index_table_control.drag_start, add="+")
        self.index_dataset_table.bind("<B1-Motion>", self.index_table_control.drag_motion, add="+")
        self.index_dataset_table.bind("<ButtonRelease-1>", self.index_table_control.drag_end, add="+")

        self.add_index_button.config(command=self.index_table_control.add_search_dir)
        self.update_index_button.config(command=self.index_table_control.sync_index)
        self.delete_index_button.config(command=self.index_table_control.delete_search_dir)
        self.rebuild_index_button.config(command=self.index_table_control.rebuild_index)

        self.theme_combobox.bind("<<ComboboxSelected>>", lambda e: self.__change_theme())
        self.open_setting_file_button.config(command=lambda: FileOperation.open_file(Setting.config_path))
        self.open_repertory_button.config(command=self.__check_for_update)

        self.drop_target_register(DND_FILES)
        self.dnd_bind('<<Drop>>', self.__on_drop)

    @Decorator.send_task
    def __env_init(self) -> None:
        self.search_control.set_similarity_threshold(self.setting.get_config("function", "similarity_threshold"))
        self.index_table_control.refresh_index_dataset_table()
        self.update_threads_count_scale.set(value=self.setting.get_config("function", "max_work_thread"))
        if self.setting.get_config("function", "auto_update_index"):
            self.auto_update_btn.invoke()
            self.index_table_control.sync_index(show_message=False)
        else:
            self.index_table_control.update_index_tip()
        self.after(self.setting.schedule_save_interval, self.__schedule_save)

    def __change_theme(self, setting_theme=False) -> None:
        style = Style()
        if setting_theme:
            valid_theme_names = style.theme_names()
            valid_theme_name = self.setting.get_config("function", "ui_style")
            valid_theme_name = valid_theme_name if valid_theme_name in valid_theme_names else "superhero"
            self.theme_combobox.current(valid_theme_names.index(valid_theme_name))
        theme_cbo_value = self.theme_combobox.get()
        self.theme_combobox.selection_clear()
        style.theme_use(theme_cbo_value)
        style.configure('TNotebook.Tab', font=('微软雅黑', 12))
        style.configure("Treeview", rowheight=50)
        self.filter_control._sync_filter_btn_style()

    def __on_drop(self, event: TkinterDnD.DnDEvent) -> None:
        file_paths_str: str = getattr(event, "data")
        file_paths = FileOperation.extract_file_paths(file_paths_str)
        tab_id = self.switch_tab.index(self.switch_tab.select())
        if tab_id == 0:
            self.search_control.search_by_browser(file_paths[0])
        elif tab_id == 1:
            for dir_path in file_paths:
                self.index_table_control.add_search_dir(dir_path)

    def __schedule_save(self) -> None:
        self.search_tools.save_index()
        self.after(self.setting.schedule_save_interval, self.__schedule_save)
    
    def destroy(self) -> None:
        try:
            self.setting.modity_config("function", "ui_style", self.theme_combobox.get())
            self.setting.modity_config("function", "auto_update_index", self.auto_update_btn.instate(['selected']))
            self.setting.modity_config("function", "max_work_thread", int(float(self.update_threads_count_scale.get())))
            self.setting.modity_config("function", "similarity_threshold", int(float(self.filter_panel.sim_scale.get())))
            self.setting.save_settings()
            self.setting.clean_log()
            self.search_tools.destroy()
            self.search_tools.save_index()
            FileOperation.clear_folder_all(Setting.temp_image_path)
            self.search_tools.set_force_end_update(True)
        except Exception as e:
            messagebox.showerror("错误", str(e))
        finally:
            super().destroy()

    @Decorator.send_task
    def __check_for_update(self) -> None:
        from utils import UpdateChecker

        result = UpdateChecker.check()
        if result.error is not None:
            messagebox.showerror(
                "检查更新失败",
                f"无法检查更新：{result.error}\n\n请检查网络连接后重试。"
            )
            return

        if result.has_update:
            self._show_update_dialog(result)
        else:
            messagebox.showinfo(
                "检查更新",
                f"当前版本：v{WinInfo.version}\n"
                f"你使用的已是最新版本！\n\n"
                f"仓库地址：{WinInfo.repo_url}"
            )

    def _show_update_dialog(self, result) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("发现新版本")
        win_width, win_height = 520, 480
        x = (self.winfo_screenwidth() - win_width) // 2
        y = (self.winfo_screenheight() - win_height) // 2
        dialog.geometry(f"{win_width}x{win_height}+{x}+{y}")
        dialog.minsize(480, 380)
        dialog.grab_set()

        bottom_frame = tk.Frame(dialog)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=15, pady=(10, 18))

        link_label = tk.Label(
            bottom_frame,
            text="下载增量更新包",
            fg="#0078D4",
            cursor="hand2",
            font=("微软雅黑", 10, "underline"),
        )
        link_label.pack(side=tk.LEFT)
        link_label.bind("<Button-1>", lambda e: (webbrowser.open(result.download_url), dialog.destroy()),)

        close_btn = tk.Button(bottom_frame, text="关闭", command=dialog.destroy, padx=15, cursor="hand2")
        close_btn.pack(side=tk.RIGHT)

        header_frame = tk.Frame(dialog)
        header_frame.pack(fill=tk.X, padx=15, pady=(15, 5))
        tk.Label(
            header_frame,
            text=f"发现新版本: v{result.latest_version}",
            font=("微软雅黑", 13, "bold"),
            anchor=tk.W,
        ).pack(anchor=tk.W)
        tk.Label(
            header_frame,
            text=f"当前版本: v{result.current_version}",
            font=("微软雅黑", 10),
            fg="gray",
            anchor=tk.W,
        ).pack(anchor=tk.W)

        tk.Frame(dialog, height=2, bd=1, relief=tk.SUNKEN).pack(fill=tk.X, padx=15, pady=5)

        notes_label = tk.Label(dialog, text="更新内容:", anchor=tk.W, font=("微软雅黑", 10))
        notes_label.pack(fill=tk.X, padx=15, pady=(5, 2))

        text_frame = tk.Frame(dialog)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 5))

        text = tk.Text(text_frame, wrap=tk.WORD, font=("微软雅黑", 9))
        scrollbar = tk.Scrollbar(text_frame, orient=tk.VERTICAL, command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)
        body = result.release_body or "暂无更新说明"
        text.insert(tk.END, body)
        text.config(state=tk.DISABLED)
        text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)



class FilterController:
    def __init__(self, core: 'CoreControl') -> None:
        self.core = core
        self._folder_all_var = tk.BooleanVar(value=True)
        self._folder_paths: list[str] = []
        self._saved_threshold: float | None = None
        self._saved_ext: str = ""
        self._saved_size_min: str = ""
        self._saved_size_min_unit: str = ""
        self._saved_size_max: str = ""
        self._saved_size_max_unit: str = ""
        self._saved_folder_selection: tuple = ()
        self._saved_folder_all: bool = True

    def init_filter_panel(self) -> None:
        fp = self.core.filter_panel
        fp.sim_scale.set(self.core.search_control.similarity_threshold)
        fp.sim_value.config(text=f"{int(self.core.search_control.similarity_threshold)}%")
        fp.sim_scale.config(
            command=lambda value: (
                fp.sim_value.config(text=f"{int(float(value))}%"),
                self.core.search_control.set_similarity_threshold(float(value))
            )
        )
        self._sync_filter_btn_style()
        self.refresh_folder_filter()
        fp.folder_select_all.config(variable=self._folder_all_var, command=self._on_folder_select_all)
        fp.folder_listbox.bind("<<ListboxSelect>>", self._on_folder_listbox_select)
        self._on_folder_select_all()

    def refresh_folder_filter(self) -> None:
        dirs = self.core.setting.get_config("index", "search_dir")
        self._folder_paths = list(dirs)
        lb = self.core.filter_panel.folder_listbox
        lb.delete(0, tk.END)
        for d in self._folder_paths:
            lb.insert(tk.END, d)

    @staticmethod
    def parse_size(text: str, unit: str) -> float | None:
        t = text.strip()
        try:
            value = float(t) if t else None
        except ValueError:
            return None
        if value is None:
            return None
        return value / 1024 if unit == "KB" else value

    def get_search_filters(self) -> tuple:
        fp = self.core.filter_panel
        ext = fp.ext_combo.get()
        size_min = self.parse_size(fp.size_min.get(), fp.size_min_unit.get())
        size_max = self.parse_size(fp.size_max.get(), fp.size_max_unit.get())
        if self._folder_all_var.get():
            folder_filters = None
        else:
            selected = fp.folder_listbox.curselection()
            folder_filters = [self._folder_paths[i] for i in selected] or None
        return ext, size_min, size_max, folder_filters

    def _on_folder_select_all(self) -> None:
        lb = self.core.filter_panel.folder_listbox
        if self._folder_all_var.get():
            lb.selection_set(0, tk.END)
        else:
            lb.selection_clear(0, tk.END)

    def _on_folder_listbox_select(self, *_) -> None:
        lb = self.core.filter_panel.folder_listbox
        all_selected = len(lb.curselection()) == lb.size()
        self._folder_all_var.set(all_selected)

    def _sync_filter_btn_style(self) -> None:
        style = Style()
        entry_bg = style.lookup('TEntry', 'fieldbackground')
        entry_fg = style.lookup('TEntry', 'foreground')
        self.core.filter_btn.config(bg=entry_bg, fg=entry_fg)

    def toggle_filter_panel(self) -> None:
        if self.core.filter_panel.winfo_viewable():
            self.core.filter_panel.place_forget()
        else:
            self.save_filter_state()
            fp = self.core.filter_panel
            fp.place(relx=0.01, rely=0.096, relwidth=0.395)
            fp.update_idletasks()
            fp.place(relx=0.01, rely=0.096, relwidth=0.395, height=fp.winfo_reqheight())
            fp.lift()

    def confirm_filter(self) -> None:
        self.core.filter_panel.place_forget()
        self.core.search_control.resend_last_search()

    def cancel_filter(self) -> None:
        self.restore_filter_state()
        self.core.filter_panel.place_forget()

    def on_root_click(self, event) -> None:
        if not self.core.filter_panel.winfo_viewable():
            return
        w = event.widget
        if w == self.core.filter_btn:
            return
        while w:
            if w == self.core.filter_panel or isinstance(w, str):
                return
            w = w.master
        self.cancel_filter()

    def save_filter_state(self) -> None:
        fp = self.core.filter_panel
        self._saved_threshold = self.core.search_control.similarity_threshold
        self._saved_ext = fp.ext_combo.get()
        self._saved_size_min = fp.size_min.get()
        self._saved_size_min_unit = fp.size_min_unit.get()
        self._saved_size_max = fp.size_max.get()
        self._saved_size_max_unit = fp.size_max_unit.get()
        self._saved_folder_selection = fp.folder_listbox.curselection()
        self._saved_folder_all = self._folder_all_var.get()

    def restore_filter_state(self) -> None:
        if self._saved_threshold is None:
            return
        fp = self.core.filter_panel
        self.core.search_control.set_similarity_threshold(self._saved_threshold)
        fp.sim_scale.set(self._saved_threshold)
        fp.sim_value.config(text=f"{int(self._saved_threshold)}%")
        fp.ext_combo.set(self._saved_ext)
        fp.size_min.delete(0, tk.END)
        fp.size_min.insert(0, self._saved_size_min)
        fp.size_min_unit.set(self._saved_size_min_unit)
        fp.size_max.delete(0, tk.END)
        fp.size_max.insert(0, self._saved_size_max)
        fp.size_max_unit.set(self._saved_size_max_unit)
        fp.folder_listbox.selection_clear(0, tk.END)
        for idx in self._saved_folder_selection:
            fp.folder_listbox.selection_set(idx)
        self._folder_all_var.set(self._saved_folder_all)



class SearchControl(object):
    def __init__(self, core_control: CoreControl) -> None:
        self._last_search_content: Image.Image | str = ""
        self._is_finish_search: bool = True
        self._preview_timer = ""
        self.similarity_threshold: float = 0.0
        self.core_control = core_control

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
        self.core_control.search_entry.delete(0, tk.END)
        self.core_control.search_entry.insert(0, image_path)
        image_obj = ImageOperation.parse_image_from_path(image_path)
        if image_obj is None:
            messagebox.showwarning("警告", "无法识别该图片类型！")
            return
        self.core_control.preview_canvas1.append_result(image_path, image_obj)
        self.__search_image(image_obj)

    @Decorator.send_task
    def search_image_by_clipboard(self) -> None:
        image_obj = ImageOperation.parse_image_from_clipboard_bytes()
        image_path = None
        
        if image_obj is None:
            try:
                copy_text = self.core_control.clipboard_get()
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

        self.core_control.preview_canvas1.append_result(str(image_path.absolute()), image_obj)
        self.__search_image(image_obj)

    @Decorator.send_task
    def search_image_by_text(self) -> None:
        text = self.core_control.search_entry.get().strip()
        self.core_control.preview_canvas1.clear_results()
        self.__search_image(text)

    def __search_image(self, input_data: Image.Image | str) -> None:
        if not self.core_control.setting.get_config("index", "search_dir"):
            messagebox.showinfo("提示", "请在设置选项卡索引至少一个目录！")
            return
        if not self._is_finish_search:
            return
        self._is_finish_search = False
        self._last_search_content = input_data
        self.core_control.preview_view.clear_results()

        ext, size_min, size_max, folder_filters = self.core_control.filter_control.get_search_filters()
        results = self.core_control.search_tools.checkout(
            input_data, self.similarity_threshold,
            ext, size_min, size_max, folder_filters
        )
        try:
            first_result = next(results)
        except StopIteration:
            status = self.core_control.search_tools.checkout_status
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
        if Path(first_img_path).exists():
            first_extra_info = SearchControl.generate_extra_info(first_img_path, first_sim)
            item = self.core_control.preview_view.append_result(first_img_path, *first_extra_info)
            self.core_control.preview_view.selection_set(item)
        
        for img_path, similarity in results:
            if Path(img_path).exists():
                extra_info = SearchControl.generate_extra_info(img_path, similarity)
                self.core_control.preview_view.append_result(img_path, *extra_info)
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
        self.core_control.setting.modity_config("index", "max_match_count", min(max_match_count, 100))
        self.core_control.search_tools.update_max_match_count(max_match_count)
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
        results = self.core_control.preview_view.get_show_results()
        current_selection = self.core_control.preview_view.selection()
        self.core_control.preview_view.destroy()
        self.core_control.setting.modity_config("function", "preview_mode", mode)
        if mode == "detail_info":
            self.core_control.preview_view = DetailListView(
                self.core_control.preview_container,
                {"大小": 100, "修改时间": 160, "相似度": 100}
            )
        else:
            self.core_control.preview_view = ThumbnailGridView(self.core_control.preview_container)
        self.core_control.bind_event()
        for result in results:
            img_path, *extra_info = result
            self.core_control.preview_view.append_result(img_path, *extra_info)
        self.core_control.preview_view.selection_set(*current_selection)

    def preview_found_image(self, event: tk.Event) -> None:
        @Decorator.send_task
        def _preview() -> None:
            try:
                first_item = selection[0]
                image_path = self.core_control.preview_view.item(first_item)[0]
                image_obj = ImageOperation.parse_image_from_path(image_path)
                if image_obj is not None:
                    self.core_control.preview_canvas2.append_result(image_path, image_obj)
            except KeyError:
                return
        selection = self.core_control.preview_view.selection()
        if not selection:
            return
        if self._preview_timer:
            self.core_control.after_cancel(self._preview_timer)
        self._preview_timer = self.core_control.after(100, _preview)



class IndexTableControl(object):
    def __init__(self, core_control: CoreControl) -> None:
        self.core_control = core_control
        self._is_updating: bool = False
        self._drag_source: str | None = None
        self._drag_active: bool = False
        self._drop_target: str | None = None
        self._insert_before: bool | None = None
        self._drag_ghost: tk.Toplevel | None = None

    def update_index_tip(self) -> None:
        self.core_control.index_tip_label.config(
            text=f"当前索引图库({self.core_control.search_tools.valid_index_count}张图片)"
        )
        self._is_updating = False

    def add_search_dir(self, dir_path: str = "") -> None:
        if dir_path != "" and not Path(dir_path).is_dir():
            return
        if dir_path == "":
            dir_path = filedialog.askdirectory(title="选择索引文件夹")
            if not dir_path:
                return
        search_dirs: list = self.core_control.setting.get_config("index", "search_dir")
        if dir_path in search_dirs:
            messagebox.showinfo("提示", "新索引的目录已包含在当前索引目录中！")
            return
        for search_dir in search_dirs:
            if Path(dir_path).is_relative_to(search_dir):
                messagebox.showinfo("提示", "该文件夹是索引目录的子文件夹！")
                return
        search_dirs.append(dir_path)
        self.refresh_index_dataset_table()
        self.core_control.setting.save_settings()

    def rebuild_index(self) -> None:
        answer = messagebox.askyesno("提示", "重建索引极其耗时，\n您确定要进行重建吗？")
        if not answer:
            return
        try:
            self.core_control.search_tools.reset_index()
        except (FileNotFoundError, KeyError):
            pass
        self.sync_index()

    def refresh_index_dataset_table(self) -> None:
        tb = self.core_control.index_dataset_table
        all_items = tb.get_children()
        all_show_dir = {tb.item(node, 'values')[1] for node in all_items}
        for index_id, item in enumerate(all_items, 1):
            _, search_dir = tb.item(item, "values")
            tb.item(item, values=(index_id, search_dir))
        search_dirs = self.core_control.setting.get_config("index", "search_dir")
        all_items_count = len(all_items) + 1
        for search_dir in search_dirs:
            if search_dir not in all_show_dir:
                tb.insert("", tk.END, values=(all_items_count, search_dir))
                all_items_count += 1
        self.core_control.filter_control.refresh_folder_filter()

    def drag_start(self, event: tk.Event) -> None:
        tb = self.core_control.index_dataset_table
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

        tb = self.core_control.index_dataset_table
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

        # 高亮「源数据将落在此行」的位置
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
            tb = self.core_control.index_dataset_table
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

            search_dirs: list = self.core_control.setting.get_config("index", "search_dir")
            dir_to_move = search_dirs.pop(source_idx)
            search_dirs.insert(target_idx, dir_to_move)

            tb.move(self._drag_source, "", target_idx)
            for i, item in enumerate(tb.get_children(), 1):
                _, dir_path = tb.item(item, "values")
                tb.item(item, values=(i, dir_path))

            tb.selection_set(self._drag_source)
            self.core_control.filter_control.refresh_folder_filter()
        finally:
            self._drag_clear_state()

    def _create_drag_ghost(self, event: tk.Event) -> None:
        source = self._drag_source
        if source is None:
            return
        tb = self.core_control.index_dataset_table
        values = tb.item(source, "values")
        dir_path = values[1] if len(values) > 1 else ""

        ghost = tk.Toplevel(tb)
        ghost.overrideredirect(True)
        ghost.attributes("-alpha", 0.75, "-topmost", True)

        label = tk.Label(ghost, text=str(dir_path), anchor="w", padx=12, pady=6,)
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

    @Decorator.send_task
    @Decorator.redirect_output
    def sync_index(self, show_message: bool = True) -> None:
        self.core_control.delete_index_button.config(state=tk.DISABLED)
        self.core_control.rebuild_index_button.config(state=tk.DISABLED)
        self.core_control.update_index_button.config(
            text="终止索引更新", 
            command=lambda: self.core_control.search_tools.set_force_end_update(True)
        )
        self._is_updating = True
        self.__check_queue()
        self.core_control.search_tools.remove_nonexists()
        for image_dir in self.core_control.setting.get_config("index", "search_dir"):
            if Path(image_dir).exists():
                self.core_control.search_tools.update_index(
                    image_dir,
                    int(float(self.core_control.update_threads_count_scale.get()))
                )
        self.core_control.update_index_button.config(text="更新索引目录", command=self.sync_index)
        self.core_control.delete_index_button.config(state=tk.ACTIVE)
        self.core_control.rebuild_index_button.config(state=tk.ACTIVE)
        if show_message:
            messagebox.showinfo("提示", "索引更新完成！")
        self.core_control.after(1000, self.update_index_tip)
        self.core_control.search_tools.set_force_end_update(False)
        self._is_updating = False

    @Decorator.send_task
    @Decorator.redirect_output
    def delete_search_dir(self) -> None:
        selected = self.core_control.index_dataset_table.selection()
        if not selected:
            return
        answer = messagebox.askyesno("提示", "你确定要删除选中目录吗？")
        if not answer:
            return
        self._is_updating = True
        self.__check_queue()
        dirs_to_delete = []
        search_dir: list = self.core_control.setting.get_config("index", "search_dir")
        for item in selected:
            delete_search_dir = self.core_control.index_dataset_table.item(item, 'values')[1]
            dirs_to_delete.append(delete_search_dir)
            search_dir.remove(delete_search_dir)
            self.core_control.index_dataset_table.delete(item)
        self.refresh_index_dataset_table()
        for dir_path in dirs_to_delete:
            self.core_control.search_tools.remove_files_in_directory(dir_path)
        self.core_control.search_tools.remove_nonexists()
        self.core_control.setting.save_settings()
        self.core_control.after(1000, self.update_index_tip)

    def __check_queue(self) -> None:
        try:
            while True:
                message = Decorator.progress_queue.get_nowait()
                self.core_control.index_tip_label.config(text=message)
        except Exception:
            pass
        if self._is_updating:
            self.core_control.after(200, self.__check_queue)



class MenuControl(object):
    ACTIVE_BORDER_WIDTH = 6
    def __init__(self, core_control: CoreControl) -> None:
        self.core_control = core_control

    def __get_item_files(self, event: tk.Event, preview_widget: BasicImagePreviewView) -> list[Path]:
        selected_items = preview_widget.selection()
        current_selected_item = preview_widget.identify_item(event)
        if current_selected_item == "":
            return []
        if current_selected_item in selected_items:
            return [Path(preview_widget.item(item)[0]) for item in selected_items]
        preview_widget.selection_set(current_selected_item)
        return [Path(preview_widget.item(current_selected_item)[0])]

    def create_right_click_menu(self, event: tk.Event, widget = None) -> None:
        if widget is None:
            widget = event.widget
        if not isinstance(widget, BasicImagePreviewView):
            return
        selected_files = self.__get_item_files(event, widget)
        if len(selected_files) == 0:
            return
        exists_files: list[Path] = [f for f in selected_files if f.exists()]
        if len(selected_files) == 1 and len(exists_files) == 1:
            file_path = selected_files[0]
            menu_items = [
                ("复制图片", lambda: FileOperation.copy_files(file_path)),
                ("复制路径", lambda: FileOperation.copy_filepaths(file_path, tk=self.core_control)),
                ("图片另存为", lambda: ImageOperation.save_as_image(file_path)),
                ("打开图片", lambda: FileOperation.open_file(file_path)),
                ("打开文件夹", lambda: FileOperation.open_file(file_path, True))
            ]
        elif len(selected_files) > 1 and len(exists_files) != 0:
            menu_items = [
                ("复制图片", lambda: FileOperation.copy_files(*selected_files)),
                ("复制路径", lambda: FileOperation.copy_filepaths(*selected_files, tk=self.core_control)),
                ("图片另存为", lambda: FileOperation.save_to_dir(*selected_files, dest_dir=filedialog.askdirectory(), is_binary=True, inplace=False))
            ]
        else:
            messagebox.showinfo("提示", "选中文件不存在！")
            return
        menu = tk.Menu(tearoff=0, activeborderwidth=self.ACTIVE_BORDER_WIDTH)
        for label, cmd in menu_items:
            menu.add_command(label=label, command=cmd, compound=tk.LEFT)
        
        menu.post(event.x_root, event.y_root)
        menu.bind("<Unmap>", lambda e: menu.destroy())

    def create_preview_setting_menu(self) -> None:
        btn = self.core_control.more_options_button
        frame1 = self.core_control.preview_frame1
        menu = tk.Menu(tearoff=0, activeborderwidth=self.ACTIVE_BORDER_WIDTH)
        menu.add_command(label="详情模式", command=lambda: self.core_control.search_control.set_preview_mode("detail_info"))
        menu.add_command(label="图标模式", command=lambda: self.core_control.search_control.set_preview_mode("medium_ico"))
        menu.add_separator()
        menu.add_command(label="结果数: 10", command=lambda: self.core_control.search_control.set_preview_result_count(10))
        menu.add_command(label="结果数: 30", command=lambda: self.core_control.search_control.set_preview_result_count(30))
        menu.add_command(label="结果数: 50", command=lambda: self.core_control.search_control.set_preview_result_count(50))
        menu.add_command(label="结果数: 100", command=lambda: self.core_control.search_control.set_preview_result_count(100))

        frame1_right = frame1.winfo_rootx() + frame1.winfo_width()
        menu_font = tkfont.Font(font=menu.cget("font"))
        menu_width = int(menu_font.measure("结果数: 100") * 1.75)
        menu.post(
            frame1_right - menu_width,
            btn.winfo_rooty() + WinInfo.TkS(25)
        )
        menu.bind("<Unmap>", lambda e: menu.destroy())

    def double_click_open_file(self, event: tk.Event, widget = None) -> None:
        if widget is None:
            widget = event.widget
        if isinstance(widget, BasicImagePreviewView):
            selected_files = self.__get_item_files(event, widget)
        elif isinstance(widget, Treeview):
            selected_files = [Path(widget.item(widget.selection()[0], "values")[1])]
        else:
            selected_files = []
        if len(selected_files) == 0:
            return
        selected_file = selected_files[0]
        if not selected_file.exists():
            messagebox.showinfo("提示", "文件不存在！")
            return
        else:
            FileOperation.open_file(selected_file)

