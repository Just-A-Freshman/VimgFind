from __future__ import annotations

from pathlib import Path
from tkinter import font as tkfont
from tkinter import messagebox, filedialog
from typing import TYPE_CHECKING
import subprocess
import tkinter as tk

from ttkbootstrap import Treeview, Menu

from config.settings import TkS
from utils.i18n import _
from views.widgets import BasicImagePreviewView, PreviewCanvasView
import utils.file_ops as file_ops
import utils.image_ops as image_ops

if TYPE_CHECKING:
    from .app_controller import AppController


class MenuController:
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
    
    @staticmethod
    def __run_custom_command(selected_files: list[Path], raw_command: str) -> None:
        for file_path in selected_files:
            path_str = str(file_path)
            resolved = raw_command.replace("$image_path", path_str)
            resolved = resolved.replace("$image_dir", str(file_path.parent))
            resolved = resolved.replace("$filename", file_path.name)
            resolved = resolved.replace("$basename", file_path.stem)
            resolved = resolved.replace("$ext", file_path.suffix)
            try:
                subprocess.Popen(resolved, shell=True)
            except Exception as e:
                messagebox.showerror("错误", _("自定义命令执行失败: {err}\n命令: {cmd}", err=str(e), cmd=resolved))

    def __create_single_file_menu(self, widget, selected_file: Path) -> Menu:
        menu = Menu(self.app.view, tearoff=0, activeborderwidth=TkS(3))
        # custom_items = self.app.setting.app.custom_menu_items
        # if custom_items:
        #     menu.add_separator()
        #     for item in custom_items:
        #         label = item.get("label", _("未命名"))
        #         cmd = item.get("command", "")
        #         menu.add_command(label=label, command=lambda f=selected_files, c=cmd: run_custom_command(f, c))
        menu.add_command(label=_("复制图片"), command=lambda: file_ops.copy_filepaths(selected_file, tk=self.app.view))
        menu.add_command(label=_("复制路径"), command=lambda: file_ops.copy_filepaths(selected_file, tk=self.app.view))
        menu.add_command(label=_("图片另存为"), command=lambda: image_ops.save_as_image(selected_file))
        menu.add_command(label=_("删除图片"), command=lambda: self.delete_files(selected_file, widget=widget))
        menu.add_separator()
        menu.add_command(label=_("打开图片"), command=lambda: file_ops.open_file(selected_file))
        menu.add_command(label=_("打开文件夹"), command=lambda: file_ops.open_file(selected_file, True))
        return menu

    def __create_multi_file_menu(self, parent, selected_files: list[Path]) -> Menu:
        menu = Menu(parent, tearoff=0, activeborderwidth=TkS(3))
        menu.add_command(label=_("复制图片"), command=lambda: file_ops.copy_files(*selected_files))
        menu.add_command(label=_("复制路径"), command=lambda: file_ops.copy_filepaths(*selected_files, tk=self.app.view))
        menu.add_command(label=_("图片另存为"), command=lambda: file_ops.save_to_dir(*selected_files, dest_dir=filedialog.askdirectory(), is_binary=True, inplace=False))
        menu.add_command(label=_("删除图片"), command=lambda: self.delete_files(*selected_files, widget=parent))
        return menu
    
    def __create_adjustment_menu(self, parent) -> Menu:
        menu = Menu(parent, tearoff=0, activeborderwidth=TkS(3))
        model_menu = Menu(parent, tearoff=0)
        ctrl = self.app.search_controller
        for label, mode in (
            (_("详情模式"), "detail_info"), (_("中等图标"), "medium_ico"),
            (_("大图标"), "big_ico"), (_("超大图标"), "huge_ico")
        ):
            menu.add_command(label=label, command=lambda m=mode: ctrl.set_preview_mode(m))  # type:ignore
        
        menu.add_separator()
        for count in (10, 30, 50, 100):
            menu.add_command(label=_("结果数: {count}", count=count), command=lambda c=count: ctrl.set_preview_result_count(c))
        
        menu.add_separator()
        menu.add_cascade(label=_("切换模型"), menu=model_menu)
        if self.app.index_controller.is_updating:
            model_menu.add_command(label=_("索引更新中，暂不可用"), state=tk.DISABLED)
        else:
            for model in self.app.model_controller.get_downloaded_models():
                model_menu.add_command(
                    label=model.meta.name,
                    command=lambda model=model: self.app.model_controller.switch_model(model.meta.id, resend_search=True)
                )
        return menu

    def show_selected_image_menu(self, event: tk.Event, widget=None) -> None:
        if widget is None:
            widget = event.widget
        if not isinstance(widget, BasicImagePreviewView):
            return
        selected_files = self.__get_item_files(event, widget)
        if len(selected_files) == 0:
            return
        exists_files: list[Path] = [f for f in selected_files if f.exists()]
        if len(selected_files) == 1 and len(exists_files) == 1:
            menu = self.__create_single_file_menu(widget, selected_files[0])
        elif len(selected_files) > 1 and len(exists_files) != 0:
            menu = self.__create_multi_file_menu(widget, selected_files)
        else:
            messagebox.showinfo(_("提示"), _("选中文件不存在！"))
            return
        menu.post(event.x_root, event.y_root)
        menu.bind("<Unmap>", lambda e: menu.destroy())

    def show_adjustment_menu(self) -> None:
        # adjustment_menu = self.__create_preview_setting_menu(event.widget)
        # frame1_right = event.widget.winfo_rootx() + event.widget.winfo_width()
        # menu_font = tkfont.Font(font=adjustment_menu.cget("font"))
        # menu_width = int(menu_font.measure("-") * 21)
        # adjustment_menu.post(frame1_right - menu_width, event.widget.winfo_rooty() + TkS(25))
        # adjustment_menu.bind("<Unmap>", lambda e: adjustment_menu.destroy())
        pass

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
        self.app.index_controller.update_index_tip()
