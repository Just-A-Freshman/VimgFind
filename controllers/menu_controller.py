from __future__ import annotations

from pathlib import Path
from tkinter import font as tkfont
from tkinter import messagebox, filedialog
from typing import TYPE_CHECKING

import tkinter as tk
import logging

from ttkbootstrap import Treeview, Menu

from config.settings import TkS
from utils.i18n import _
from views.widgets import BasicImagePreviewView, PreviewCanvasView
import utils.shortcut as shortcut
import utils.file_ops as file_ops
import utils.image_ops as image_ops
import utils.decorators as decorators

if TYPE_CHECKING:
    from .app_controller import AppController


class CustomMenuItem:
    def __init__(
        self,
        label: str = "",
        is_visible: bool = False,
        shortcut: list[str] | None = None,
        batch_mode: bool = False,
        command: str = "",
    ) -> None:
        self.label = label
        self.is_visible = is_visible
        self.shortcut = shortcut or []
        self.batch_mode = batch_mode
        self.command = command

    @classmethod
    def from_dict(cls, data: dict) -> CustomMenuItem:
        return cls(
            label=data.get("label", ""),
            is_visible=data.get("is_visible", False),
            shortcut=data.get("shortcut", []),
            batch_mode=data.get("batch_mode", False),
            command=data.get("command", ""),
        )

    def resolve_single(self, file_path: Path) -> str:
        cmd = self.command
        cmd = cmd.replace("$image_path", str(file_path))
        cmd = cmd.replace("$image_dir", str(file_path.parent))
        cmd = cmd.replace("$filename", file_path.name)
        cmd = cmd.replace("$basename", file_path.stem)
        cmd = cmd.replace("$ext", file_path.suffix)
        return cmd

    def resolve_batch(self, file_paths: list[Path]) -> str:
        cmd = self.command
        cmd = cmd.replace("$image_path", " ".join(f"\"{str(p)}\"" for p in file_paths))
        cmd = cmd.replace("$image_dir", " ".join(f"\"{str(p.parent)}\"" for p in file_paths))
        cmd = cmd.replace("$filename", " ".join(f"\"{p.name}\"" for p in file_paths))
        cmd = cmd.replace("$basename", " ".join(f"\"{p.stem}\"" for p in file_paths))
        cmd = cmd.replace("$ext", " ".join(f"\"{p.suffix}\"" for p in file_paths))
        return cmd


class MenuController:
    def __init__(self, app_controller: AppController) -> None:
        self.app = app_controller

    def on_custom_shortcut(self, event) -> str | None:
        custom_shortcut = shortcut.build_shortcut(event)
        pv = self.app.view.search_tab.preview_view
        selected_ids = pv.selection()
        if not selected_ids:
            return

        for item in self.app.setting.app.custom_menu_items:
            item = CustomMenuItem.from_dict(item)
            if item.shortcut == custom_shortcut:
                paths = [Path(pv.item(fid)[0]) for fid in selected_ids]
                paths = [p for p in paths if p.exists()]
                if paths:
                    self.__run_custom_command(paths, item)
                    return "break"

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

    def show_adjustment_menu(self, widget) -> None:
        def get_label(i) -> str:
            try:
                return adjustment_menu.entrycget(i, 'label')
            except tk.TclError:
                return ""

        adjustment_menu = self.__create_adjustment_menu()
        winfo_right = widget.winfo_rootx() + widget.winfo_width()
        menu_font = tkfont.Font(font=adjustment_menu.cget("font"))
        menu_width = max(menu_font.measure(get_label(i)) for i in range(adjustment_menu.index(tk.END) or 0 + 1)) + TkS(65)
        adjustment_menu.post(winfo_right - menu_width, widget.winfo_rooty() + TkS(25))
        adjustment_menu.bind("<Unmap>", lambda e: adjustment_menu.destroy())

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

    def __get_item_files(self, event: tk.Event, preview_widget: BasicImagePreviewView) -> list[Path]:
        selected_items = preview_widget.selection()
        current_selected_item = preview_widget.identify_item(event)
        if current_selected_item == "":
            return []
        if current_selected_item in selected_items:
            return [Path(preview_widget.item(item)[0]) for item in selected_items]
        preview_widget.selection_set(current_selected_item)
        return [Path(preview_widget.item(current_selected_item)[0])]

    @decorators.send_task
    def __run_custom_command(self, selected_files: list[Path], menu_item: CustomMenuItem) -> None:
        if menu_item.batch_mode:
            resolved = menu_item.resolve_batch(selected_files)
            returncode, stdout, stderr = file_ops.run_cmd(resolved)
            if returncode != 0:
                logging.error(f"执行命令：{resolved}, 命令输出：{stdout}, 错误原因：{stderr}")
                self.app.search_controller.show_toast(
                    _("{count}张图片的命令执行失败。", count=len(selected_files))
                )
            else:
                self.app.search_controller.show_toast(_("{label}成功！", label=menu_item.label))
        else:
            error_count = 0
            for file_path in selected_files:
                resolved = menu_item.resolve_single(file_path)
                returncode, stdout, stderr = file_ops.run_cmd(resolved)
                if returncode != 0:
                    logging.error(f"执行命令失败：{resolved}, 错误原因：{stderr}")
                    error_count += 1
            self.app.search_controller.show_toast(
                _("命令执行成功！") if error_count == 0
                else _("{count}张图片的命令执行失败。", count=error_count)
            )

    def __append_custom_menu(self, menu: Menu, selected_files: list[Path]) -> None:
        custom_items = self.app.setting.app.custom_menu_items
        if not custom_items:
            return
        for item in custom_items:
            item = CustomMenuItem.from_dict(item)
            if not item.is_visible:
                continue
            menu.add_command(
                label=item.label,
                command=lambda f=selected_files, m=item: self.__run_custom_command(f, m),
            )
        if menu.index(tk.END) is not None:
            menu.add_separator()

    def __create_single_file_menu(self, widget, selected_file: Path) -> Menu:
        menu = Menu(self.app.view, tearoff=0, activeborderwidth=TkS(3), bd=0)
        self.__append_custom_menu(menu, [selected_file])
        menu.add_command(label=_("复制图片"), command=lambda: file_ops.copy_filepaths(selected_file, tk=self.app.view))
        menu.add_command(label=_("复制路径"), command=lambda: file_ops.copy_filepaths(selected_file, tk=self.app.view))
        menu.add_command(label=_("图片另存为"), command=lambda: image_ops.save_as_image(selected_file))
        menu.add_command(label=_("删除图片"), command=lambda: self.delete_files(selected_file, widget=widget))
        menu.add_separator()
        menu.add_command(label=_("打开图片"), command=lambda: file_ops.open_file(selected_file))
        menu.add_command(label=_("打开文件夹"), command=lambda: file_ops.open_file(selected_file, True))
        return menu

    def __create_multi_file_menu(self, widget, selected_files: list[Path]) -> Menu:
        menu = Menu(self.app.view, tearoff=0, activeborderwidth=TkS(3))
        self.__append_custom_menu(menu, selected_files)
        menu.add_command(label=_("复制图片"), command=lambda: file_ops.copy_files(*selected_files))
        menu.add_command(label=_("复制路径"), command=lambda: file_ops.copy_filepaths(*selected_files, tk=self.app.view))
        menu.add_command(label=_("图片另存为"), command=lambda: file_ops.save_to_dir(*selected_files, dest_dir=filedialog.askdirectory(), is_binary=True, inplace=False))
        menu.add_command(label=_("删除图片"), command=lambda: self.delete_files(*selected_files, widget=widget))
        return menu

    def __create_adjustment_menu(self) -> Menu:
        menu = Menu(self.app.view, tearoff=0, activeborderwidth=TkS(3))
        model_menu = Menu(menu, tearoff=0)
        ctrl = self.app.search_controller
        for label, mode in (
            (_("详情模式"), "detail_info"),
            (_("中等图标"), "medium_ico"),
            (_("大图标"), "big_ico"),
            (_("超大图标"), "huge_ico"),
        ):
            menu.add_command(label=label, command=lambda m=mode: ctrl.set_preview_mode(m))  # type:ignore

        menu.add_separator()
        for count in (10, 50, 100, 300):
            menu.add_command(label=_("结果数: {count}", count=count), command=lambda c=count: ctrl.set_preview_result_count(c))

        menu.add_separator()
        menu.add_cascade(label=_("切换模型"), menu=model_menu)
        if self.app.index_controller.is_updating:
            model_menu.add_command(label=_("索引更新中，暂不可用"), state=tk.DISABLED)
        else:
            for model in self.app.model_controller.get_downloaded_models():
                model_menu.add_command(
                    label=model.meta.name,
                    command=lambda model=model: self.app.model_controller.switch_model(model.meta.id, resend_search=True),
                )
        return menu
