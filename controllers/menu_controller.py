from __future__ import annotations

from typing import TYPE_CHECKING
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, filedialog
from tkinter import font as tkfont
from tkinter.ttk import Treeview

import utils.file_ops as file_ops
import utils.image_ops as image_ops
from config.settings import TkS
from views.widgets import BasicImagePreviewView

if TYPE_CHECKING:
    from .app_controller import AppController


class MenuController(object):
    ACTIVE_BORDER_WIDTH = TkS(3)

    def __init__(self, app_controller: AppController) -> None:
        self.app = app_controller

    def __get_item_files(self, event: tk.Event, preview_widget: BasicImagePreviewView) -> list[Path]:
        selected_items = preview_widget.selection()
        current_selected_item = preview_widget.identify_item(event)
        if current_selected_item == "":
            return []
        if current_selected_item in selected_items:
            return [Path(preview_widget.item(item)[0]) for item in selected_items]
        preview_widget.selection_set(current_selected_item)
        return [Path(preview_widget.item(current_selected_item)[0])]

    def create_right_click_menu(self, event: tk.Event, widget=None) -> None:
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
                ("复制图片", lambda: file_ops.copy_files(file_path)),
                ("复制路径", lambda: file_ops.copy_filepaths(file_path, tk=self.app.view)),
                ("图片另存为", lambda: image_ops.save_as_image(file_path)),
                ("打开图片", lambda: file_ops.open_file(file_path)),
                ("打开文件夹", lambda: file_ops.open_file(file_path, True))
            ]
        elif len(selected_files) > 1 and len(exists_files) != 0:
            menu_items = [
                ("复制图片", lambda: file_ops.copy_files(*selected_files)),
                ("复制路径", lambda: file_ops.copy_filepaths(*selected_files, tk=self.app.view)),
                ("图片另存为", lambda: file_ops.save_to_dir(*selected_files, dest_dir=filedialog.askdirectory(), is_binary=True, inplace=False))
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
        tab = self.app.view.search_tab
        btn = tab.more_options_button
        frame1 = tab.preview_frame1
        menu = tk.Menu(tearoff=0, activeborderwidth=self.ACTIVE_BORDER_WIDTH)
        menu.add_command(label="详情模式", command=lambda: self.app.search_controller.set_preview_mode("detail_info"))
        menu.add_command(label="中等图标", command=lambda: self.app.search_controller.set_preview_mode("medium_ico"))
        menu.add_command(label="大图标", command=lambda: self.app.search_controller.set_preview_mode("big_ico"))
        menu.add_command(label="超大图标", command=lambda: self.app.search_controller.set_preview_mode("huge_ico"))
        menu.add_separator()
        menu.add_command(label="结果数: 10", command=lambda: self.app.search_controller.set_preview_result_count(10))
        menu.add_command(label="结果数: 30", command=lambda: self.app.search_controller.set_preview_result_count(30))
        menu.add_command(label="结果数: 50", command=lambda: self.app.search_controller.set_preview_result_count(50))
        menu.add_command(label="结果数: 100", command=lambda: self.app.search_controller.set_preview_result_count(100))
        menu.add_separator()
        model_menu = tk.Menu(menu)
        for model in self.app.model_controller.get_downloaded_models():
            model_menu.add_command(
                label=model.meta.name, 
                command=lambda model=model: self.app.model_controller.switch_model(model.meta.id, resend_search=True)
            )
        menu.add_cascade(label='切换模型', menu=model_menu)

        frame1_right = frame1.winfo_rootx() + frame1.winfo_width()
        menu_font = tkfont.Font(font=menu.cget("font"))
        menu_width = int(menu_font.measure("-") * 21)
        menu.post(
            frame1_right - menu_width,
            btn.winfo_rooty() + TkS(25)
        )
        menu.bind("<Unmap>", lambda e: menu.destroy())

    def double_click_open_file(self, event: tk.Event, widget=None) -> None:
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
            file_ops.open_file(selected_file)
