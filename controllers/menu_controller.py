from __future__ import annotations

from typing import TYPE_CHECKING
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, filedialog
from tkinter import font as tkfont
from ttkbootstrap import Treeview

import utils.file_ops as file_ops
import utils.image_ops as image_ops
from utils.i18n import _
from config.settings import TkS
from views.widgets import BasicImagePreviewView, PreviewCanvasView

if TYPE_CHECKING:
    from .app_controller import AppController


class MenuController:
    app: AppController
    __slots__ = ("app",)

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
            menu = self.app.view.click_menu.single_file_menu
            menu.entryconfig(0, command=lambda: file_ops.copy_files(*selected_files))
            menu.entryconfig(1, command=lambda: file_ops.copy_filepaths(*selected_files, tk=self.app.view))
            menu.entryconfig(2, command=lambda: image_ops.save_as_image(*selected_files))
            menu.entryconfig(3, command=lambda: self.delete_files(*selected_files, widget=widget))
            menu.entryconfig(5, command=lambda: file_ops.open_file(selected_files[0]))
            menu.entryconfig(6, command=lambda: file_ops.open_file(selected_files[0], True))
        elif len(selected_files) > 1 and len(exists_files) != 0:
            menu = self.app.view.click_menu.multi_file_menu
            menu.entryconfig(0, command=lambda: file_ops.copy_files(*selected_files))
            menu.entryconfig(1, command=lambda: file_ops.copy_filepaths(*selected_files, tk=self.app.view))
            menu.entryconfig(2, command=lambda: file_ops.save_to_dir(*selected_files, dest_dir=filedialog.askdirectory(), is_binary=True, inplace=False))
            menu.entryconfig(3, command=lambda: self.delete_files(*selected_files, widget=widget))
        else:
            messagebox.showinfo(_("提示"), _("选中文件不存在！"))
            return
        menu.post(event.x_root, event.y_root)

    def create_preview_setting_menu(self) -> None:
        tab = self.app.view.search_tab
        ctrl = self.app.search_controller
        menu = self.app.view.click_menu.preview_setting_menu
        menu.entryconfig(0, command=lambda: ctrl.set_preview_mode("detail_info"))
        menu.entryconfig(1, command=lambda: ctrl.set_preview_mode("medium_ico"))
        menu.entryconfig(2, command=lambda: ctrl.set_preview_mode("big_ico"))
        menu.entryconfig(3, command=lambda: ctrl.set_preview_mode("huge_ico"))
        menu.entryconfig(5, command=lambda: ctrl.set_preview_result_count(10))
        menu.entryconfig(6, command=lambda: ctrl.set_preview_result_count(30))
        menu.entryconfig(7, command=lambda: ctrl.set_preview_result_count(50))
        menu.entryconfig(8, command=lambda: ctrl.set_preview_result_count(100))

        model_menu = self.app.view.click_menu.model_menu
        model_menu.delete(0, tk.END)
        if self.app.index_controller.is_updating:
            model_menu.add_command(label=_("索引更新中，暂不可用"), state=tk.DISABLED)
        else:
            for model in self.app.model_controller.get_downloaded_models():
                model_menu.add_command(
                    label=model.meta.name,
                    command=lambda model=model: self.app.model_controller.switch_model(model.meta.id, resend_search=True)
                )

        frame1_right = tab.preview_frame1.winfo_rootx() + tab.preview_frame1.winfo_width()
        menu_font = tkfont.Font(font=menu.cget("font"))
        menu_width = int(menu_font.measure("-") * 21)
        menu.post(frame1_right - menu_width, tab.more_options_button.winfo_rooty() + TkS(25))

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
            messagebox.showinfo(_("提示"), _("文件不存在！"))
            return
        else:
            file_ops.open_file(selected_file)

    def delete_files(self, *file_paths: str | Path, widget: BasicImagePreviewView) -> None:
        assert self.app.search_tools
        tab = self.app.view.search_tab
        answer = messagebox.askokcancel(_("提示"), _("你确定要删除这{count}张图片吗？", count=len(file_paths)))
        if not answer:
            return
        
        selection = widget.selection()
        if isinstance(widget, PreviewCanvasView):
            try:
                tab.preview_view.delete(*selection)
            except tk.TclError:
                pass
            if tab.preview_canvas1.selection() == tab.preview_canvas2.selection():
                tab.preview_canvas1.clear()
                tab.preview_canvas2.clear()
            else:
                widget.delete(*selection)
        else:
            for i in (tab.preview_canvas1, tab.preview_canvas2):
                if len(i.selection()) != 0 and i.selection()[0] in selection:
                    i.clear()
            widget.delete(*selection)
        
        for file_path in file_paths:
            file_ops.delete_file(file_path, hard=False)
        self.app.search_tools.remove_files(list(map(str, file_paths)))
