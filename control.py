from tkinter import messagebox, filedialog, ttk
from ttkbootstrap import Style
import tkinter as tk
from pathlib import Path
import datetime
import os


from ui import WinGUI
from setting import Setting
from utils import FileOperation, Decorator
from core import SearchTool


from PIL import Image, ImageTk, ImageOps, UnidentifiedImageError



class Control(WinGUI):
    def __init__(self) -> None:
        self.setting = Setting()
        self.search_tools = SearchTool(self.setting)
        super().__init__()
        self.__event_bind()
        self.__style_config()
        self.__env_init()
        self.__check_queue()

    def __event_bind(self) -> None:
        self.add_index_button.config(command=self.add_search_dir)
        self.update_index_button.config(command=self.sync_index)
        self.delete_index_button.config(command=self.delete_search_dir)
        self.rebuild_index_button.config(command=self.rebuild_index)
        self.search_button.config(command=self.search_image)
        self.preview_canvas1.config(cursor="hand2")
        self.preview_canvas2.config(cursor="hand2")
        self.result_table.bind("<<TreeviewSelect>>", self.preview_found_image)
        self.result_table.bind("<Button-3>", self.__create_menu)
        self.preview_canvas1.bind("<Button-3>", self.__create_menu)
        self.preview_canvas2.bind("<Button-3>", self.__create_menu)
        self.result_table.bind("<Double-Button-1>", self.__double_click_open_file)
        self.index_dataset_table.bind("<Double-Button-1>", self.__double_click_open_file)
        self.preview_canvas1.bind("<Double-Button-1>", self.__double_click_open_file)
        self.preview_canvas2.bind("<Double-Button-1>", self.__double_click_open_file)
        for column in self.result_table["columns"]:
            self.result_table.heading(column, command=lambda column=column: self.__sort_column(column, False))

    def __env_init(self) -> None:
        self.after(self.setting.schedule_save_interval, self.__schedule_save)
        self.refresh_index_dataset_table()
        if self.setting.get_config_property("auto_update_index"):
            self.sync_index(show_message=False)

    def __style_config(self) -> None:
        style = Style()
        style.theme_use(self.setting.get_config_property("ui_style"))

    def __get_widget_selected_file(self, event: tk.Event) -> Path:
        selected_widget: tk.Widget = event.widget
        selected_file = Path(".")
        if isinstance(selected_widget, ttk.Treeview):
            item = selected_widget.identify_row(event.y)
            if item:
                selected_widget.selection_set(item)
                selected_file = Path(selected_widget.item(item, 'text'))
        elif isinstance(selected_widget, tk.Canvas):
            if hasattr(selected_widget, "image_path"):
                selected_file = Path(getattr(selected_widget, "image_path"))
        else:
            pass
        return selected_file

    def __double_click_open_file(self, event: tk.Event) -> None:
        selected_file = self.__get_widget_selected_file(event)
        if not selected_file.exists():
            messagebox.showinfo("提示", "文件不存在！")
            return
        elif selected_file == Path("."):
            return
        else:
            FileOperation.open_file(selected_file)

    def __create_menu(self, event: tk.Event) -> None:
        selected_file = self.__get_widget_selected_file(event)
        menu_state = tk.ACTIVE if selected_file.exists() else tk.DISABLED
        
        menu_items = [
            ("复制图片", lambda: FileOperation.copy_file(selected_file)),
            ("打开图片", lambda: FileOperation.open_file(selected_file)),
            ("打开文件夹", lambda: FileOperation.open_file(selected_file, highlight=True))
        ]
        
        menu = tk.Menu(tearoff=0)
        for label, cmd in menu_items:
            menu.add_command(label=label, command=cmd, compound=tk.LEFT, state=menu_state)
        
        menu.post(event.x_root, event.y_root)

    def __sort_column(self, col: str, reverse: bool) -> None:
        data = [(self.result_table.set(k, col), k) for k in self.result_table.get_children("")]
        if col == "相似度" or col == "大小":
            data.sort(key = lambda x: f"{x[0]:0>10}", reverse=reverse)
        else:
            data.sort(reverse=reverse)
        for index, (_, k) in enumerate(data):
            self.result_table.move(k, "", index)
        self.result_table.heading(col, command=lambda: self.__sort_column(col, not reverse))

    def __arrange_search_result(self, similarity: float, image_path: str) -> tuple[str, str, str, str]:
        image_path_obj = Path(image_path)
        mtime = datetime.datetime.fromtimestamp(os.path.getmtime(image_path))
        content = (
            image_path_obj.name,
            f"{os.path.getsize(image_path_obj) / 1024 / 1024:.2f}MB",
            mtime.strftime("%Y-%m-%d %H:%M:%S"),
            f"{similarity:.2f}%"
        )
        return content

    def __check_queue(self) -> None:
        try:
            while True:
                message = Decorator.progress_queue.get_nowait()
                self.index_tip_label.config(text=message)
        except Exception:
            pass

        self.after(300, self.__check_queue)

    def add_search_dir(self) -> None:
        dir_path = filedialog.askdirectory(title="选择索引文件夹")
        if not dir_path:
            return
        search_dirs: list = self.setting.get_config_property("search_dir")
        if dir_path in search_dirs:
            messagebox.showinfo("提示", "新索引的目录已包含在当前索引目录中！")
            return
        for search_dir in search_dirs:
            if Path(dir_path).is_relative_to(search_dir):
                return
        search_dirs.append(dir_path)
        self.setting.save_settings()
        self.refresh_index_dataset_table()

    def rebuild_index(self) -> None:
        answer = messagebox.askyesno("提示", "重建索引极其耗时，\n您确定要进行重建吗？")
        if not answer:
            return
        try:
            self.search_tools.reset_index()
        except (FileNotFoundError, KeyError):
            pass
        self.sync_index()

    def refresh_index_dataset_table(self) -> None:
        all_nodes = self.index_dataset_table.get_children()
        all_show_dir = {self.index_dataset_table.item(node, 'values')[1] for node in all_nodes}
        index_id = len(all_nodes)
        for search_dir in self.setting.get_config_property("search_dir"):
            if search_dir in all_show_dir:
                continue
            index_id += 1
            self.index_dataset_table.insert("", tk.END, values=(index_id, search_dir), text=str(search_dir))

    def __create_image(self, image_path: Path, canvas: tk.Canvas) -> int:
        if not image_path.exists():
            return -1
        canvas_width = canvas.winfo_width() or 400
        canvas_height = canvas.winfo_height() or 300
        x = canvas_width // 2
        y = canvas_height // 2
        try:
            with Image.open(image_path) as img:
                img: Image.Image = ImageOps.exif_transpose(img)
                img.thumbnail((canvas_width, canvas_height), Image.Resampling.BICUBIC)
                image_file = ImageTk.PhotoImage(img)
        except UnidentifiedImageError:
            return -1
        canvas.delete(tk.ALL)
        setattr(canvas, "image", image_file)
        setattr(canvas, "image_path", image_path)
        return canvas.create_image(x, y, anchor=tk.CENTER, image=image_file)

    @Decorator.send_task
    @Decorator.redirect_output
    def sync_index(self, show_message: bool = True) -> None:
        index_button = (self.delete_index_button, self.update_index_button, self.rebuild_index_button)
        for btn in index_button:
            btn.config(state=tk.DISABLED)

        self.search_tools.remove_nonexists()
        for image_dir in self.setting.get_config_property('search_dir'):
            if Path(image_dir).exists():
                self.search_tools.update_ir_index(image_dir)
        for btn in index_button:
            btn.config(state=tk.ACTIVE)
        if show_message:
            messagebox.showinfo("提示", "索引更新完成！")

    @Decorator.send_task
    @Decorator.redirect_output
    def delete_search_dir(self) -> None:
        selected = self.index_dataset_table.selection()
        if not selected:
            return
        answer = messagebox.askyesno("提示", "你确定要删除选中目录吗？")
        if not answer:
            return
            
        dirs_to_delete = []
        search_dir: list = self.setting.get_config_property("search_dir")
        for item in selected:
            delete_search_dir = self.index_dataset_table.item(item, 'values')[1]
            dirs_to_delete.append(delete_search_dir)
            search_dir.remove(delete_search_dir)
            self.index_dataset_table.delete(item)

        for dir_path in dirs_to_delete:
            self.search_tools.remove_files_in_directory(dir_path)
            
        self.search_tools.remove_nonexists()
        self.setting.save_settings()

    @Decorator.send_task
    def search_image(self) -> None:
        if not self.setting.get_config_property("search_dir"):
            messagebox.showinfo("提示", "请在设置选项卡索引至少一个目录！")
            return
        
        image_path = filedialog.askopenfilename(
            filetypes=[("图片文件", "*" + ";*".join(Setting.accepted_exts))]
        )
        if not image_path:
            return
        
        self.search_entry.delete(0, tk.END)
        self.search_entry.insert(0, image_path)
        image_id = self.__create_image(Path(image_path), self.preview_canvas1)
        if image_id == -1:
            messagebox.showwarning("警告", "无法识别该图片类型！")
            return

        self.result_table.delete(*self.result_table.get_children())
        results = self.search_tools.checkout(image_path)
        try:
            first_result = next(results)
        except StopIteration:
            messagebox.showinfo("提示", "索引中没有任何图片，\n也许你还没有更新索引？")
            return
        
        first_content = self.__arrange_search_result(*first_result)
        self.result_table.insert('', tk.END, values=first_content, text=str(first_result[1]), iid=0)
        self.result_table.selection_set(0)
        
        for similarity, image_path in results:
            content = self.__arrange_search_result(similarity, image_path)
            self.result_table.insert('', tk.END, values=content, text=str(image_path))

    @Decorator.send_task
    def preview_found_image(self, event: tk.Event) -> None:
        selection = self.result_table.selection()
        if not selection:
            return
        
        first_item = selection[0]
        image_path = self.result_table.item(first_item, 'text')
        if not image_path:
            return
        self.__create_image(Path(image_path), self.preview_canvas2)

    def __schedule_save(self) -> None:
        self.search_tools.save_index()
        self.after(self.setting.schedule_save_interval, self.__schedule_save)
    
    def destroy(self):
        self.search_tools.save_index()
        super().destroy()

