from __future__ import annotations

import re
import shlex
from pathlib import Path
from tkinter import font as tkfont
from tkinter import messagebox, filedialog, simpledialog
from typing import TYPE_CHECKING

import tkinter as tk
import logging

from ttkbootstrap import Treeview, Menu

from config.settings import TkS, Setting
from utils.i18n import _
from views.widgets import BasicImagePreviewView, PreviewCanvasView
import utils.shortcut as shortcut
import utils.file_ops as file_ops
import utils.image_ops as image_ops
import utils.decorators as decorators

if TYPE_CHECKING:
    from .app_controller import AppController


class CustomMenuItem:
    VAR_RE = re.compile(r'\{(\w+)((?:\|[^}]+)*)\}')
    ASK_VARS = frozenset({'ask_dir', 'ask_file', 'ask_files', 'ask_input', 'ask_int', 'ask_float'})
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
        self.__ask_values: dict[str, str | list[str]] = {}

    @classmethod
    def from_dict(cls, data: dict) -> CustomMenuItem:
        return cls(
            label=data.get("label", ""),
            is_visible=data.get("is_visible", False),
            shortcut=data.get("shortcut", []),
            batch_mode=data.get("batch_mode", False),
            command=data.get("command", ""),
        )
    
    def resolve_ask(self) -> bool:
        tokens = shlex.split(self.command)
        for token in tokens:
            for m in CustomMenuItem.VAR_RE.finditer(token):
                name = m.group(1)
                if name not in CustomMenuItem.ASK_VARS or name in self.__ask_values:
                    continue
                val = self.__prompt_ask(name)
                if val is None:
                    self.__ask_values.clear()
                    return False
                self.__ask_values[name] = val
        return True

    def resolve(self, file_paths: list[Path]) -> list[str]:
        tokens = shlex.split(self.command)
        file_vals = self._compute_file_values(file_paths)
        result: list[str] = []
        for token in tokens:
            result.extend(self.__resolve_token(token, file_vals))
        return result
    
    @staticmethod
    def __parse_modifiers(mod_str: str) -> dict[str, str]:
            if not mod_str:
                return {}
            s = mod_str.lstrip('|')
            mods: dict[str, str] = {}
            i = 0
            while i < len(s):
                if s[i:].startswith('raw'):
                    mods['raw'] = ''
                    i += 3
                elif s[i:].startswith('sep='):
                    mods['sep'] = s[i + 4:]
                    i = len(s)
                    continue
                else:
                    i += 1
                if i < len(s) and s[i] == '|':
                    i += 1
            return mods

    def _compute_file_values(self, file_paths: list[Path]) -> dict[str, str | list[str]]:
        if self.batch_mode:
            return {
                'paths':[str(p) for p in file_paths],
                'first_dir':str(file_paths[0].parent),
                'count':str(len(file_paths)),
            }
        first = file_paths[0]
        return {
            'path':str(first),
            'dir':str(first.parent),
            'name':first.name,
            'noext':first.stem,
            'ext':first.suffix,
        }

    def __resolve_token(self, token: str, file_vals: dict) -> list[str]:
        matches = list(CustomMenuItem.VAR_RE.finditer(token))
        if not matches:
            return [token]

        if len(matches) == 1 and matches[0].group(0) == token:
            name = matches[0].group(1)
            val = self.__lookup_var(name, file_vals, matches[0].group(2))
            if val is None:
                return [token]
            if isinstance(val, list):
                return val
            return [str(val)]

        result = token
        for m in matches:
            name = m.group(1)
            val = self.__lookup_var(name, file_vals, m.group(2))
            if val is None:
                continue
            replacement = ' '.join(str(v) for v in val) if isinstance(val, list) else str(val)
            result = result.replace(m.group(0), replacement, 1)
        return [result]

    def __lookup_var(self, name: str, file_vals: dict, mod_str: str) -> str | list[str] | None:
        if name in self.__ask_values:
            val = self.__ask_values[name]
        elif name in file_vals:
            val = file_vals[name]
        else:
            return None

        if not isinstance(val, list):
            return val

        mods = self.__parse_modifiers(mod_str)
        if 'sep' in mods:
            return mods['sep'].join(val)
        return val

    def __prompt_ask(self, var_name: str) -> str | list[str] | None:
        if var_name == 'ask_dir':
            v = filedialog.askdirectory(title=_("选择文件夹"))
            return v if v else None
        elif var_name == 'ask_file':
            v = filedialog.askopenfilename(title=_("选择文件"))
            return v if v else None
        elif var_name == 'ask_files':
            v = filedialog.askopenfilenames(title=_("选择文件"))
            return list(v) if v else None
        elif var_name == 'ask_input':
            return simpledialog.askstring(_("输入"), _("请输入："))
        elif var_name == 'ask_int':
            v = simpledialog.askinteger(_("输入"), _("请输入整数："))
            return str(v) if v is not None else None
        elif var_name == 'ask_float':
            v = simpledialog.askfloat(_("输入"), _("请输入数字："))
            return str(v) if v is not None else None
        return None


class MenuController:
    def __init__(self, app_controller: AppController) -> None:
        self.app = app_controller
        self.__last_single_image_save_dir: Path | None = None
        self.__last_multi_image_save_dir: Path | None = None

    def on_custom_shortcut(self, event) -> str | None:
        custom_shortcut = shortcut.build_shortcut(event)
        pv = self.app.view.search_tab.preview_view
        selected_ids = pv.selection()
        if not selected_ids:
            return

        for item in self.app.setting.app.custom_menu_items:
            item = CustomMenuItem.from_dict(item)
            if item.shortcut == custom_shortcut and item.shortcut not in shortcut.INNER_SHORTCUT:
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

    def save_as_image(self, *src_paths: Path) -> None:
        if len(src_paths) == 1:
            save_path = filedialog.asksaveasfilename(
                filetypes=[(f"{i}(*{i})", f"*{i}") for i in Setting.accepted_exts if i not in [".psd"]],
                initialfile=src_paths[0].name,
                initialdir=self.__last_single_image_save_dir,
                defaultextension=src_paths[0].suffix
            )
            if save_path:
                dest_path = Path(save_path)
                self.__last_single_image_save_dir = dest_path.parent
                image_ops.save_as_image(src_paths[0], dest_path)
        else:
            save_dir = filedialog.askdirectory(initialdir=self.__last_multi_image_save_dir)
            if save_dir:
                self.__last_multi_image_save_dir = Path(save_dir)
                file_ops.save_to_dir(*src_paths, dest_dir=self.__last_multi_image_save_dir, is_binary=True, inplace=False)

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
        if not menu_item.resolve_ask():
            return

        if menu_item.batch_mode:
            cmd = menu_item.resolve(selected_files)
            returncode, stdout, stderr = file_ops.run_cmd(cmd)
            if returncode != 0:
                logging.error(f"执行命令：{cmd}, 命令输出：{stdout}, 错误原因：{stderr}")
                self.app.search_controller.show_toast(
                    _("{count}张图片的命令执行失败。", count=len(selected_files))
                )
            else:
                self.app.search_controller.show_toast(_("{label}成功！", label=menu_item.label))
        else:
            error_count = 0
            for file_path in selected_files:
                cmd = menu_item.resolve([file_path])
                returncode, stdout, stderr = file_ops.run_cmd(cmd)
                if returncode != 0:
                    logging.error(f"执行命令失败：{cmd}, 错误原因：{stderr}")
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
        menu.add_command(label=_("复制图片"), command=lambda: file_ops.copy_files(selected_file))
        menu.add_command(label=_("复制路径"), command=lambda: file_ops.copy_filepaths(selected_file, tk=self.app.view))
        menu.add_command(label=_("图片另存为"), command=lambda: self.save_as_image(selected_file))
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
        menu.add_command(label=_("图片另存为"), command=lambda: self.save_as_image(*selected_files))
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
            if mode == self.app.setting.app.preview_mode: label += "✓"
            menu.add_command(label=label, command=lambda m=mode: ctrl.set_preview_mode(m))  # type:ignore

        menu.add_separator()
        for count in (10, 50, 100, 300):
            label = _("结果数: {count}", count=count)
            if count == self.app.setting.app.max_match_count: label += "✓"
            menu.add_command(label=label, command=lambda c=count: ctrl.set_preview_result_count(c))

        menu.add_separator()
        menu.add_cascade(label=_("切换模型"), menu=model_menu)
        if self.app.index_controller.is_updating:
            model_menu.add_command(label=_("索引更新中，暂不可用"), state=tk.DISABLED)
        else:
            for model in self.app.model_controller.get_downloaded_models():
                model_menu.add_command(
                    label=(model.meta.name + "✓") if model.meta.id == self.app.setting.app.current_model else model.meta.name,
                    command=lambda model=model: self.app.model_controller.switch_model(model.meta.id, resend_search=True),
                )
        return menu
