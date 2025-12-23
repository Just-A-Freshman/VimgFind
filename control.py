from tkinter import messagebox, filedialog, ttk
from ttkbootstrap import Style
import tkinter as tk
from pathlib import Path
from typing import Literal
import os


from ui import WinGUI
from widgets import BasicPreviewView, DetailListView, ThumbnailGridView, PreviewResult
from setting import Setting
from utils import FileOperation, ImageOperation, Decorator
from search_tools import SearchTool



from PIL import Image



class CoreControl(WinGUI):
    def __init__(self) -> None:
        super().__init__()
        self.setting = Setting()
        self.search_tools = SearchTool(self.setting)
        self.index_table_control = IndexTableControl(self)
        self.search_control = SearchControl(self)
        self.search_control.set_preview_mode("medium_ico")
        self.bind_event()
        self.__style_config()
        self.__env_init()
        self.__check_queue()

    @Decorator.send_task
    def bind_event(self) -> None:
        # 搜索控制项
        self.search_by_browser_btn.config(command=self.search_control.search_by_browser)
        self.search_by_clipboard_btn.config(command=self.search_control.search_image_by_clipboard)
        self.search_entry.bind("<Return>", lambda e: self.search_control.search_image_by_text())
        self.more_options_button.config(command=self.__create_preview_setting_menu)

        # 附加功能项
        self.preview_view.bind("<<ItemviewSelect>>", self.search_control.preview_found_image)
        self.preview_view.bind("<Control-a>", lambda e: self.preview_view.selection_set(tk.ALL))
        preview_widgets = (self.preview_canvas1, self.preview_canvas2, self.preview_view)
        for w in preview_widgets:
            w.bind("<Button-3>", lambda e, w=w: self.create_right_click_menu(e, w))
            w.bind("<Double-Button-1>", lambda e, w=w: self.double_click_open_file(e, w))

        # 索引目录控制项
        self.index_dataset_table.bind("<Double-Button-1>", self.double_click_open_file)
        self.add_index_button.config(command=self.index_table_control.add_search_dir)
        self.update_index_button.config(command=self.index_table_control.sync_index)
        self.delete_index_button.config(command=self.index_table_control.delete_search_dir)
        self.rebuild_index_button.config(command=self.index_table_control.rebuild_index)

    @Decorator.send_task
    def __env_init(self) -> None:
        self.after(self.setting.schedule_save_interval, self.__schedule_save)
        self.index_table_control.refresh_index_dataset_table()
        if self.setting.get_config("function", "auto_update_index"):
            self.index_table_control.sync_index(show_message=False)

    def __style_config(self) -> None:
        style = Style()
        style.theme_use(self.setting.get_config("function", "ui_style"))

    def __get_item_files(self, event: tk.Event, preview_widget: BasicPreviewView) -> list[Path]:
        selected_items = preview_widget.selection()
        current_selected_item = preview_widget.identify_item(event)
        if current_selected_item == "":
            return []
        if current_selected_item in selected_items:
            return [Path(item) for item in selected_items]
        preview_widget.selection_set(current_selected_item)
        return [Path(current_selected_item)]
    
    def double_click_open_file(self, event: tk.Event, widget = None) -> None:
        if widget is None:
            widget = event.widget
        selected_files = self.__get_item_files(event, widget)
        if len(selected_files) == 0:
            return
        selected_file = selected_files[0]
        if not selected_file.exists():
            messagebox.showinfo("提示", "文件不存在！")
            return
        else:
            FileOperation.open_file(selected_file)

    def create_right_click_menu(self, event: tk.Event, widget = None) -> None:
        if widget is None:
            widget = event.widget
        selected_files = self.__get_item_files(event, widget)
        if len(selected_files) == 0:
            return
        exists_files: list[Path] = [f for f in selected_files if f.exists()]
        menu_items = [
            ("复制图片", lambda: FileOperation.copy_files(*selected_files), len(exists_files) > 0),
            ("打开图片", lambda: FileOperation.open_file(selected_files[0]), len(exists_files) == 1),
            ("打开文件夹", lambda: FileOperation.open_file(selected_files[0], True), len(exists_files) == 1)
        ]
        
        menu = tk.Menu(tearoff=0)
        for label, cmd, active in menu_items:
            state = tk.ACTIVE if active else tk.DISABLED
            menu.add_command(label=label, command=cmd, compound=tk.LEFT, state=state)
        
        menu.post(event.x_root, event.y_root)
        menu.bind("<Unmap>", lambda e: menu.destroy())

    def __create_preview_setting_menu(self) -> None:
        btn = self.more_options_button
        menu = tk.Menu(tearoff=0)
        menu_items = [
            ("大图标", lambda: None),
            ("中等图标", lambda: self.search_control.set_preview_mode("medium_ico")),
            ("详情", lambda: self.search_control.set_preview_mode("detail_info")), 
            ("/", lambda: None),
        ] + [
            (f"结果数: {num}", lambda num=num: self.search_control.set_preview_result_count(num))
            for num in (10, 30, 50, 100)
        ]
        for label, cmd in menu_items:
            if label == "/": 
                menu.add_separator()
                continue
            menu.add_command(label=label, command=cmd, compound=tk.LEFT)
            
        menu.post(btn.winfo_rootx() - 60, btn.winfo_rooty() + 30)
        menu.bind("<Unmap>", lambda e: menu.destroy())

    def __check_queue(self) -> None:
        try:
            while True:
                message = Decorator.progress_queue.get_nowait()
                self.index_tip_label.config(text=message)
        except Exception:
            pass

        self.after(300, self.__check_queue)

    def __schedule_save(self) -> None:
        self.search_tools.save_index()
        self.after(self.setting.schedule_save_interval, self.__schedule_save)
    
    def destroy(self) -> None:
        try:
            self.search_tools.destroy()
            self.search_tools.save_index()
            FileOperation.clear_folder_all(Setting.temp_image_path)
        except Exception as e:
            messagebox.showerror("错误", str(e))
        finally:
            super().destroy()



class SearchControl(object):
    def __init__(self, core_control: CoreControl) -> None:
        self.core_control = core_control
  
    @Decorator.send_task
    def search_by_browser(self, image_path: str | None = None) -> None:
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
        self.core_control.preview_canvas1.insert_result(image_path, image_obj)
        self.__search_image(image_obj)

    @Decorator.send_task
    def search_image_by_clipboard(self) -> None:
        image_obj = ImageOperation.get_clipboard_image_bytes()
        if image_obj is None:
            image_path = Path(self.core_control.clipboard_get())
            image_obj = ImageOperation.get_image_obj(image_path)
            if image_obj is None:
                messagebox.showinfo("提示", "无法识别剪切板中的图片数据！")
                return
        else:
            image_path = FileOperation.generate_unique_filename(Setting.temp_image_path, ".jpg")
            if os.path.getsize(Setting.temp_image_path) > 1024 * 1024 * 30:
                FileOperation.clear_folder_all(Setting.temp_image_path)
            if not image_path.parent.exists():
                Path.mkdir(Setting.temp_image_path, exist_ok=True)
            image_obj.save(image_path)
        self.core_control.preview_canvas1.insert_result(str(image_path), image_obj)
        self.__search_image(image_obj)

    @Decorator.send_task
    def search_image_by_text(self) -> None:
        text = self.core_control.search_entry.get().strip()
        self.__search_image(text)

    def __search_image(self, input_data: Image.Image | str) -> None:
        if not self.core_control.setting.get_config("index", "search_dir"):
            messagebox.showinfo("提示", "请在设置选项卡索引至少一个目录！")
            return
        self.core_control.preview_view.clear_results()
        results = self.core_control.search_tools.checkout(input_data)
        try:
            first_result = next(results)
        except StopIteration:
            if self.core_control.search_tools.is_empty_index():
                messagebox.showinfo("提示", "索引中还没有任何图像，也许\n你还没有添加并更新索引目录？")
            else:
                messagebox.showerror("错误", "图片搜索失败！\n请查看config/error.log获取错误信息！")
            return

        item = self.core_control.preview_view.insert_result(PreviewResult(*first_result))
        self.core_control.preview_view.selection_set(item)
        
        for img_path, similarity in results:
            self.core_control.preview_view.insert_result(PreviewResult(img_path, similarity))

    def set_preview_result_count(self, max_match_count: int) -> None:
        self.core_control.search_tools.update_max_match_count(max_match_count)
        image_path = self.core_control.preview_canvas1.selection()[0]
        if image_path != "" and Path(image_path).exists():
            self.search_by_browser(image_path)
        elif self.core_control.search_entry.get().strip():
            self.search_image_by_text()
        else:
            pass

    def set_preview_mode(self, mode: Literal["detail_info", "medium_ico", "huge_ico"]) -> None:
        results = self.core_control.preview_view.get_show_results()
        current_selection = self.core_control.preview_view.selection()
        print(len(current_selection))
        self.core_control.preview_view.destroy()
        if mode == "detail_info":
            self.core_control.preview_view = DetailListView(self.core_control.preview_container)
        elif mode == "medium_ico" or mode == "huge_ico":
            self.core_control.preview_view = ThumbnailGridView(self.core_control.preview_container)
        self.core_control.bind_event()
        for result in results:
            self.core_control.preview_view.insert_result(result)
        self.core_control.preview_view.selection_set(*current_selection)

    @Decorator.send_task
    def preview_found_image(self, event: tk.Event) -> None:
        selection = self.core_control.preview_view.selection()
        if not selection:
            return
        
        first_item = selection[0]
        image_obj = ImageOperation.get_image_obj(first_item)
        if image_obj is not None:
            self.core_control.preview_canvas2.insert_result(first_item, image_obj)




class IndexTableControl(object):
    def __init__(self, core_control: CoreControl) -> None:
        self.core_control = core_control

    def add_search_dir(self) -> None:
        dir_path = filedialog.askdirectory(title="选择索引文件夹")
        if not dir_path:
            return
        search_dirs: list = self.core_control.setting.get_config("index", "search_dir")
        if dir_path in search_dirs:
            messagebox.showinfo("提示", "新索引的目录已包含在当前索引目录中！")
            return
        for search_dir in search_dirs:
            if Path(dir_path).is_relative_to(search_dir):
                messagebox.showinfo("提示", "该文件夹是在索引目录的子文件夹！")
                continue
        search_dirs.append(dir_path)
        self.core_control.setting.save_settings()
        self.refresh_index_dataset_table()

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
        all_nodes = self.core_control.index_dataset_table.get_children()
        all_show_dir = {self.core_control.index_dataset_table.item(node, 'values')[1] for node in all_nodes}
        index_id = len(all_nodes)
        for search_dir in self.core_control.setting.get_config("index", "search_dir"):
            if search_dir in all_show_dir:
                continue
            index_id += 1
            self.core_control.index_dataset_table.insert("", tk.END, values=(index_id, search_dir), iid=search_dir)

    @Decorator.send_task
    @Decorator.redirect_output
    def sync_index(self, show_message: bool = True) -> None:
        index_button = (self.core_control.delete_index_button, self.core_control.update_index_button, self.core_control.rebuild_index_button)
        for btn in index_button:
            btn.config(state=tk.DISABLED)

        self.core_control.search_tools.remove_nonexists()
        for image_dir in self.core_control.setting.get_config("index", "search_dir"):
            if Path(image_dir).exists():
                self.core_control.search_tools.update_ir_index(
                    image_dir, 
                    self.core_control.setting.get_config("function", "max_work_thread")
                )
        for btn in index_button:
            btn.config(state=tk.ACTIVE)
        if show_message:
            messagebox.showinfo("提示", "索引更新完成！")

    @Decorator.send_task
    @Decorator.redirect_output
    def delete_search_dir(self) -> None:
        selected = self.core_control.index_dataset_table.selection()
        if not selected:
            return
        answer = messagebox.askyesno("提示", "你确定要删除选中目录吗？")
        if not answer:
            return
            
        dirs_to_delete = []
        search_dir: list = self.core_control.setting.get_config("index", "search_dir")
        for item in selected:
            delete_search_dir = self.core_control.index_dataset_table.item(item, 'values')[1]
            dirs_to_delete.append(delete_search_dir)
            search_dir.remove(delete_search_dir)
            self.core_control.index_dataset_table.delete(item)

        for dir_path in dirs_to_delete:
            self.core_control.search_tools.remove_files_in_directory(dir_path)
            
        self.core_control.search_tools.remove_nonexists()
        self.core_control.setting.save_settings()


