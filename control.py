from tkinter import messagebox, filedialog, ttk
from ttkbootstrap import Style
import tkinter as tk
from pathlib import Path
import datetime
import os

from ui import WinGUI
from setting import Setting
import utils


from PIL import Image, ImageTk, ImageOps



class Control(WinGUI):
    def __init__(self) -> None:
        self.setting = Setting()
        self.utils = utils.Utils(self.setting.config)
        self.image_file = None
        super().__init__()
        self.__event_bind()
        self.__style_config()
        self.check_queue()

    def __event_bind(self) -> None:
        self.add_index_button.config(command=self.add_search_dir)
        self.update_index_button.config(command=self.sync_index)
        self.delete_index_button.config(command=self.delete_search_dir)
        self.rebuild_index_button.config(command=self.rebuild_index)
        self.search_button.config(command=self.search_image)
        self.result_table.bind("<<TreeviewSelect>>", lambda e: self.preview_image())
        self.result_table.bind("<Button-3>", self.create_menu)
        self.result_table.bind("<Double-Button-1>", self.double_click_open_file)
        self.index_dataset_table.bind("<Double-Button-1>", self.double_click_open_file)
        for column in self.result_table["columns"]:
            self.result_table.heading(column, command=lambda column=column: self.sort_column(column, False))

        self.refresh_index_dataset_table()

    def __style_config(self) -> None:
        style = Style()
        style.theme_use(self.setting.config["ui_style"])

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
            self.index_dataset_table.insert("", "end", values=(index_id, search_dir), text=str(search_dir))

    @utils.Decorator.send_task
    @utils.Decorator.redirect_output
    def sync_index(self) -> None:
        self.utils.remove_nonexists()
        for image_dir in self.setting.config['search_dir']:
            need_index = self.utils.index_target_dir(image_dir)
            self.utils.update_ir_index(need_index)
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
        self.search_entry.delete(0, "end")
        self.search_entry.insert(0, image_path)
        self.result_table.delete(*self.result_table.get_children())
        name_index = self.utils._get_name_index()
        results = self.utils.checkout(image_path, name_index)

        if not results:
            messagebox.showinfo("提示", "索引中没有任何图片，\n也许你还没有更新索引？")
            return
        
        for similarity, image_path in results:
            image_path = Path(image_path)
            mtime = datetime.datetime.fromtimestamp(os.path.getmtime(image_path))
            content = [
                image_path.name,
                f"{os.path.getsize(image_path) / 1024 / 1024:.2f}MB",
                mtime.strftime("%Y-%m-%d %H:%M:%S"),
                f"{similarity:.2f}%"
            ]
            self.result_table.insert('', "end", values=content, text=str(image_path))

    @utils.Decorator.send_task
    def preview_image(self) -> None:
        selection = self.result_table.selection()
        if not selection:
            return
        
        first_item = selection[0]
        image_path = self.result_table.item(first_item, 'text')
        if not image_path or not Path(image_path).exists():
            return

        canvas_width = self.preview_canvas.winfo_width() or 400
        canvas_height = self.preview_canvas.winfo_height() or 300
        center_x = canvas_width // 2
        center_y = canvas_height // 2

        with Image.open(image_path) as img:
            img: Image.Image = ImageOps.exif_transpose(img)
            width, height = img.size
            dpi = img.info.get('dpi')
            dpi = "" if dpi is None else f"{int(dpi[0])} dpi"
            self.preview_label.config(
                text=f"大小信息\n{width}x{height}\t{dpi}\n\n文件路径\n{image_path}"
            )
            img.thumbnail((canvas_width, canvas_height), Image.Resampling.BICUBIC)
            self.image_file = ImageTk.PhotoImage(img)
            self.preview_canvas.delete("all")
            self.preview_canvas.create_image(center_x, center_y, anchor=tk.CENTER, image=self.image_file)

    def double_click_open_file(self, event) -> None:
        table: ttk.Treeview = event.widget
        if not isinstance(table, ttk.Treeview):
            return
        item = table.identify_row(event.y)
        if not item:
            return
        selected_file = Path(table.item(item, 'text'))
        utils.FileOperation.open_file(selected_file)

    def create_menu(self, event) -> None:
        item = self.result_table.identify_row(event.y)
        if not item:
            return
        self.result_table.selection_set(item)
        selected_file = Path(self.result_table.item(item, 'text'))
          
        menu = tk.Menu(tearoff=0)
        menu.add_command(
            label="复制图片", 
            command=lambda: utils.FileOperation.copy_file(selected_file), 
            compound='left'
        )
        menu.add_command(
            label="打开图片", 
            command=lambda: utils.FileOperation.open_file(selected_file), 
            compound='left'
        )
        menu.add_command(
            label="打开文件夹", 
            command=lambda: utils.FileOperation.open_file(selected_file, highlight=True), 
            compound='left'
        )
        menu.post(event.x_root, event.y_root)

    def sort_column(self, col: str, reverse: bool) -> None:
        data = [(self.result_table.set(k, col), k) for k in self.result_table.get_children("")]
        if col == "相似度" or col == "大小":
            data.sort(key = lambda x: f"{x[0]:0>10}", reverse=reverse)
        else:
            data.sort(reverse=reverse)
        for index, (_, k) in enumerate(data):
            self.result_table.move(k, "", index)
        self.result_table.heading(col, command=lambda: self.sort_column(col, not reverse))

    def check_queue(self):
        try:
            while True:
                message = utils.Decorator.progress_queue.get_nowait()
                self.index_tip_label.config(text=message)
        except Exception:
            pass

        self.after(500, self.check_queue)

