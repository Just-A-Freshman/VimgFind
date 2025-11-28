from tkinter import messagebox, filedialog, ttk
from ttkbootstrap import Style
import tkinter as tk
from pathlib import Path
import datetime
import os

from ui import WinGUI
from setting import Setting
import utils


from PIL import Image, ImageTk, ImageOps, UnidentifiedImageError



class Control(WinGUI):
    def __init__(self) -> None:
        self.setting = Setting()
        self.utils = utils.Utils(self.setting.config)
        super().__init__()
        self.__event_bind()
        self.__style_config()
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

        self.refresh_index_dataset_table()

    def __style_config(self) -> None:
        style = Style()
        style.theme_use(self.setting.config["ui_style"])

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
            utils.FileOperation.open_file(selected_file)

    def __create_menu(self, event: tk.Event) -> None:
        selected_file = self.__get_widget_selected_file(event)
        menu_state = tk.ACTIVE if selected_file.exists() else tk.DISABLED
        
        menu_items = [
            ("复制图片", lambda: utils.FileOperation.copy_file(selected_file)),
            ("打开图片", lambda: utils.FileOperation.open_file(selected_file)),
            ("打开文件夹", lambda: utils.FileOperation.open_file(selected_file, highlight=True))
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

    def __check_queue(self):
        try:
            while True:
                message = utils.Decorator.progress_queue.get_nowait()
                self.index_tip_label.config(text=message)
        except Exception:
            pass

        self.after(300, self.__check_queue)

    def add_search_dir(self) -> None:
        dir_path = filedialog.askdirectory(title="选择索引文件夹")
        if not dir_path:
            return
        search_dirs: list = self.setting.config['search_dir']
        if dir_path in search_dirs:
            messagebox.showinfo("提示", "新索引的目录已包含在当前索引目录中！")
            return
        for search_dir in search_dirs:
            if Path(dir_path).is_relative_to(search_dir):
                return
        
        self.setting.config['search_dir'].append(dir_path)
        self.setting.save_settings()
        self.refresh_index_dataset_table()

    def rebuild_index(self) -> None:
        answer = messagebox.askyesno("提示", "重建索引极其耗时，\n您确定要进行重建吗？")
        if not answer:
            return
        try:
            os.remove(self.setting.config["index_path"])
            os.remove(self.setting.config["name_index_path"])
        except FileNotFoundError:
            pass
        self.sync_index()

    def refresh_index_dataset_table(self) -> None:
        all_nodes = self.index_dataset_table.get_children()
        all_show_dir = {self.index_dataset_table.item(node, 'values')[1] for node in all_nodes}
        index_id = len(all_nodes)
        for search_dir in self.setting.config["search_dir"]:
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

    @utils.Decorator.send_task
    @utils.Decorator.redirect_output
    def sync_index(self) -> None:
        index_button = (self.delete_index_button, self.update_index_button, self.rebuild_index_button)
        for btn in index_button:
            btn.config(state=tk.DISABLED)

        self.utils.remove_nonexists()
        for image_dir in self.setting.config['search_dir']:
            need_index = self.utils.index_target_dir(image_dir)
            self.utils.update_ir_index(need_index)
        for btn in index_button:
            btn.config(state=tk.ACTIVE)
        messagebox.showinfo("提示", "索引更新完成！")

    @utils.Decorator.send_task
    @utils.Decorator.redirect_output
    def delete_search_dir(self) -> None:
        selected = self.index_dataset_table.selection()
        if not selected:
            return
        answer = messagebox.askyesno("提示", "你确定要删除选中目录吗？")
        if not answer:
            return
            
        dirs_to_delete = []
        for item in selected:
            delete_search_dir = self.index_dataset_table.item(item, 'values')[1]
            dirs_to_delete.append(delete_search_dir)
            self.setting.config["search_dir"].remove(delete_search_dir)
            self.index_dataset_table.delete(item)

        for dir_path in dirs_to_delete:
            self.utils.remove_files_in_directory(dir_path)
            
        self.utils.remove_nonexists()
        self.setting.save_settings()

    @utils.Decorator.send_task
    def search_image(self) -> None:
        if not self.setting.config["search_dir"]:
            messagebox.showinfo("提示", "请在设置选项卡索引至少一个目录！")
            return
        
        image_path = filedialog.askopenfilename(filetypes=Setting.default_file_type)
        if not image_path:
            return
        
        self.search_entry.delete(0, tk.END)
        self.search_entry.insert(0, image_path)
        image_id = self.__create_image(Path(image_path), self.preview_canvas1)
        if image_id == -1:
            messagebox.showwarning("警告", "无法识别该图片类型！")
            return
        
        self.result_table.delete(*self.result_table.get_children())
        name_index = self.utils.get_name_index()
        results = self.utils.checkout(image_path, name_index)

        if not results:
            messagebox.showinfo("提示", "索引中没有任何图片，\n也许你还没有更新索引？")
            return
        
        for iid, (similarity, image_path) in enumerate(results):
            image_path = Path(image_path)
            mtime = datetime.datetime.fromtimestamp(os.path.getmtime(image_path))
            content = [
                image_path.name,
                f"{os.path.getsize(image_path) / 1024 / 1024:.2f}MB",
                mtime.strftime("%Y-%m-%d %H:%M:%S"),
                f"{similarity:.2f}%"
            ]
            self.result_table.insert('', tk.END, values=content, text=str(image_path), iid=iid)
            if iid == 0:
                self.result_table.selection_set(iid)

    @utils.Decorator.send_task
    def preview_found_image(self, event: tk.Event) -> None:
        selection = self.result_table.selection()
        if not selection:
            return
        
        first_item = selection[0]
        image_path = self.result_table.item(first_item, 'text')
        if not image_path:
            return
        self.__create_image(Path(image_path), self.preview_canvas2)

