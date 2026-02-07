from tkinter import messagebox, filedialog
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
from search_tools import SearchTool
import webbrowser


from PIL import Image


class CoreControl(WinGUI):
    def __init__(self) -> None:
        super().__init__()
        self.setting = Setting()
        self.__change_theme(setting_theme=True)
        self.search_tools = SearchTool(self.setting)
        self.index_table_control = IndexTableControl(self)
        self.search_control = SearchControl(self)
        self.menu_control = MenuControl(self)
        self.search_control.set_preview_mode(self.setting.get_config("function", "preview_mode"))
        self.__env_init()
        self.bind_event(first_time=True)
        
    def bind_event(self, first_time=False) -> None:
        # 搜索展示控制项
        self.preview_view.bind("<<ItemviewSelect>>", self.search_control.preview_found_image)
        self.preview_view.bind("<Control-a>", lambda e: self.preview_view.selection_set(tk.ALL))
        self.preview_view.bind("<Control-v>", lambda e: self.search_control.search_image_by_clipboard())
        preview_widgets = (self.preview_canvas1, self.preview_canvas2, self.preview_view)
        for w in preview_widgets:
            w.bind("<Button-3>", lambda e, w=w: self.menu_control.create_right_click_menu(e, w))
            w.bind("<Double-Button-1>", lambda e, w=w: self.menu_control.double_click_open_file(e, w))

        if not first_time:
            return
        
        # 搜索输入控制项
        self.search_by_browser_btn.config(command=self.search_control.search_by_browser)
        self.search_by_clipboard_btn.config(command=self.search_control.search_image_by_clipboard)
        self.search_entry.bind("<Return>", lambda e: self.search_control.search_image_by_text())
        self.more_options_button.config(command=self.menu_control.create_preview_setting_menu)
        
        # 索引设置项
        self.index_dataset_table.bind("<Double-Button-1>", self.menu_control.double_click_open_file)
        self.add_index_button.config(command=self.index_table_control.add_search_dir)
        self.update_index_button.config(command=self.index_table_control.sync_index)
        self.delete_index_button.config(command=self.index_table_control.delete_search_dir)
        self.rebuild_index_button.config(command=self.index_table_control.rebuild_index)

        # 常规设置项
        self.theme_combobox.bind("<<ComboboxSelected>>", lambda e: self.__change_theme())
        self.open_setting_file_button.config(command=lambda: FileOperation.open_file(Setting.config_path))
        self.open_repertory_button.config(command=lambda: webbrowser.open(r"https://github.com/Just-A-Freshman/VimgFind"))

        # 全局事件处理
        self.drop_target_register(DND_FILES)
        self.dnd_bind('<<Drop>>', self.__on_drop)

    @Decorator.send_task
    def __env_init(self) -> None:
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
        # 配置特殊Style
        style.theme_use(theme_cbo_value)
        style.configure('TNotebook.Tab', font=('微软雅黑', 12))
        style.configure("Treeview", rowheight=50)

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



class SearchControl(object):
    def __init__(self, core_control: CoreControl) -> None:
        self._last_search_content: Image.Image | str = ""
        self._is_finish_search: bool = True
        self._preview_timer: str = ""
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
        image_obj = ImageOperation.get_image_obj(image_path)
        if image_obj is None:
            messagebox.showwarning("警告", "无法识别该图片类型！")
            return
        self.core_control.preview_canvas1.append_result(image_path, image_obj)
        self.__search_image(image_obj)

    @Decorator.send_task
    def search_image_by_clipboard(self) -> None:
        image_obj = ImageOperation.get_clipboard_image_bytes()
        if image_obj is None:
            try:
                image_path = Path(self.core_control.clipboard_get())
                image_obj = ImageOperation.get_image_obj(image_path)
                if image_obj is None:
                    raise tk.TclError
            except tk.TclError:
                messagebox.showinfo("提示", "无法识别剪切板中的图片数据！")
                return
        else:
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
        results = self.core_control.search_tools.checkout(input_data)
        try:
            first_result = next(results)
        except StopIteration:
            if self.core_control.search_tools.is_empty_index():
                messagebox.showinfo("提示", "索引中还没有任何图像，也许\n你还没有添加并更新索引目录？")
            else:
                messagebox.showerror("错误", "图片搜索失败！\n请查看config/error.log获取错误信息！")
            self._is_finish_search = True
            return
        first_img_path, first_sim = first_result
        if Path(first_img_path).exists():
            first_extra_info = self.generate_extra_info(first_img_path, first_sim)
            item = self.core_control.preview_view.append_result(first_img_path, *first_extra_info)
            self.core_control.preview_view.selection_set(item)
        
        for img_path, similarity in results:
            if Path(img_path).exists():
                extra_info = self.generate_extra_info(img_path, similarity)
                self.core_control.preview_view.append_result(img_path, *extra_info)
        self._is_finish_search = True

    def generate_extra_info(self, image_path: str, similarity: float) -> tuple:
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
                image_obj = ImageOperation.get_image_obj(image_path)
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
    
    @staticmethod
    def ask_for_filename(src_path: Path) -> str:
        return filedialog.asksaveasfilename(
            defaultextension=src_path.suffix,
            filetypes=[("图片文件", f"*{src_path.suffix}")],
            initialfile=src_path.stem
        )
    
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
                ("图片另存为", lambda: FileOperation.save_as(file_path, self.ask_for_filename(file_path), True)),
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
        menu = tk.Menu(tearoff=0, activeborderwidth=self.ACTIVE_BORDER_WIDTH)
        menu.add_command(label="详情模式", command=lambda: self.core_control.search_control.set_preview_mode("detail_info"))
        menu.add_command(label="图标模式", command=lambda: self.core_control.search_control.set_preview_mode("medium_ico"))
        menu.add_separator()
        menu.add_command(label="结果数: 10", command=lambda: self.core_control.search_control.set_preview_result_count(10))
        menu.add_command(label="结果数: 30", command=lambda: self.core_control.search_control.set_preview_result_count(30))
        menu.add_command(label="结果数: 50", command=lambda: self.core_control.search_control.set_preview_result_count(50))
        menu.add_command(label="结果数: 100", command=lambda: self.core_control.search_control.set_preview_result_count(100))
        menu.add_separator()
        menu.add_command(label="过滤器", command=lambda: None)
        menu.add_command(label="清理过滤", command=lambda: None)
        menu.post(
            btn.winfo_rootx() + WinInfo.TkS(btn.winfo_width() - menu.winfo_screenmmwidth(), restore=True), 
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

