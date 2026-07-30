from __future__ import annotations

from pathlib import Path
from tkinter import font as tkfont
from tkinter import messagebox, filedialog, simpledialog
from typing import Callable, TYPE_CHECKING
import tkinter as tk
import logging
import shutil
import copy
import tempfile
import shlex
import re

from ttkbootstrap import Menu

from config.settings import TkS, Setting
from config.types import MenuItemDef
from utils.i18n import _
from views.widgets import BasicImagePreviewView, PreviewCanvasView
from views.test_dialog import TestResultDialog, TestResultItem
import utils.shortcut as shortcut
import utils.file_ops as file_ops
import utils.image_ops as image_ops
import utils.decorators as decorators

if TYPE_CHECKING:
    from .app_controller import AppController


class CustomMenuItem:
    VAR_RE = re.compile(r'\{(\w+)((?:\|[^}]+)*)\}')
    ASK_VARS = frozenset({'ask_dir', 'ask_file', 'ask_files', 'ask_input', 'ask_int', 'ask_float'})
    def __init__(self, menu_item: MenuItemDef) -> None:
        self.menu_item = menu_item
        self.__ask_values: dict[str, str | list[str]] = {}

    def resolve_ask(self) -> bool:
        tokens = self.__strip_outer_quotes(shlex.split(self.menu_item.command, posix=False))
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
        tokens = self.__strip_outer_quotes(shlex.split(self.menu_item.command, posix=False))
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

    @staticmethod
    def __strip_outer_quotes(tokens: list[str]) -> list[str]:
        result = []
        for t in tokens:
            if len(t) >= 2 and t[0] == t[-1] and t[0] in ('"', "'"):
                result.append(t[1:-1])
            else:
                result.append(t)
        return result

    def _compute_file_values(self, file_paths: list[Path]) -> dict[str, str | list[str]]:
        if self.menu_item.batch_mode:
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

    def on_menu_shortcut(self, event) -> str | None:
        custom_shortcut = shortcut.build_shortcut(event)
        preview_view = self.app.view.search_tab.preview_view
        selected_ids = preview_view.selection()
        if not selected_ids:
            return

        for item in self.app.setting.app.menu_items:
            if item.type == "separator" or item.shortcut in shortcut.INNER_SHORTCUT or item.shortcut != custom_shortcut:
                continue
            paths = [Path(preview_view.item(fid)[0]) for fid in selected_ids]
            paths = [p for p in paths if p.exists()]
            if not paths:
                continue
            if item.type == "embedded":
                self.__get_embeded_command(event, paths).get(item.name, lambda: None)()
                if item.name in ["复制图片", "复制路径"]:
                    self.app.search_controller.show_toast(_("{label}成功！", label=item.name))
            else:
                self.__run_custom_command(paths, item)
            return "break"

    def show_context_menu(self, event: tk.Event) -> None:
        if not isinstance(event.widget, BasicImagePreviewView):
            return
        selected_items = event.widget.selection()
        current_selected_item = event.widget.identify_item(event)
        if current_selected_item == "":
            return
        if current_selected_item in selected_items:
            selected_files = [Path(event.widget.item(item)[0]) for item in selected_items]
        else:
            event.widget.selection_set(current_selected_item)
            selected_files = [Path(event.widget.item(current_selected_item)[0])]
        exists_files: list[Path] = [f for f in selected_files if f.exists()]
        if len(exists_files) == 0:
            messagebox.showinfo(_("提示"), _("选中文件不存在！"))
            return
        menu = self.__create_context_menu(event, exists_files)
        menu.post(event.x_root, event.y_root)
        menu.bind("<Unmap>", lambda e: menu.destroy())

    def show_adjustment_menu(self, event: tk.Event) -> None:
        def get_label(i) -> str:
            try:
                return adjustment_menu.entrycget(i, 'label')
            except tk.TclError:
                return ""

        adjustment_menu = self.__create_adjustment_menu()
        winfo_right = event.widget.winfo_rootx() + event.widget.winfo_width()
        menu_font = tkfont.Font(font=adjustment_menu.cget("font"))
        menu_width = max(menu_font.measure(get_label(i)) for i in range(adjustment_menu.index(tk.END) or 0 + 1)) + TkS(65)
        adjustment_menu.post(winfo_right - menu_width, event.widget.winfo_rooty() + TkS(25))
        adjustment_menu.bind("<Unmap>", lambda e: adjustment_menu.destroy())

    def double_click_open_file(self, event: tk.Event) -> None:
        if not isinstance(event.widget, BasicImagePreviewView):
            return
        selected_file = Path(event.widget.item(event.widget.selection()[0])[0])
        if not selected_file.exists():
            messagebox.showinfo(_("提示"), _("文件不存在！"))
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

    def delete_files(self, event: tk.Event, selected_files: list[Path]) -> None:
        assert self.app.search_tools
        tab = self.app.view.search_tab
        if not isinstance(event.widget, BasicImagePreviewView):
            return
        answer = messagebox.askokcancel(_("提示"), _("你确定要删除这{count}张图片吗？", count=len(selected_files)))
        if not answer:
            return
        selection = event.widget.selection()
        if isinstance(event.widget, PreviewCanvasView):
            try:
                tab.preview_view.delete(*selection)
            except tk.TclError:
                pass
            if tab.preview_canvas1.selection() == tab.preview_canvas2.selection():
                tab.preview_canvas1.clear()
                tab.preview_canvas2.clear()
            else:
                event.widget.delete(*selection)
        else:
            for i in (tab.preview_canvas1, tab.preview_canvas2):
                if len(i.selection()) != 0 and i.selection()[0] in selection:
                    i.clear()
            event.widget.delete(*selection)
        for file_path in selected_files:
            file_ops.delete_file(file_path, hard=False)
        self.app.search_tools.remove_files(list(map(str, selected_files)))
        self.app.index_controller.update_index_tip()

    def __get_embeded_command(self, event: tk.Event, selected_files: list[Path]) -> dict[str, Callable]:
        return {
            "复制图片": lambda f=selected_files: file_ops.copy_files(*f),
            "复制路径": lambda f=selected_files: file_ops.copy_filepaths(*f, tk=self.app.view),
            "图片另存为": lambda f=selected_files: self.save_as_image(*f),
            "删除图片": lambda f=selected_files: self.delete_files(event, f),
            "打开图片": lambda: file_ops.open_file(selected_files[0]),
            "打开文件夹": lambda: file_ops.open_file(selected_files[0], True)
        }
    
    def __create_context_menu(self, event: tk.Event, selected_files: list[Path]) -> Menu:
        menu = Menu(self.app.view, tearoff=0, activeborderwidth=TkS(3), bd=0)
        id_command_map = self.__get_embeded_command(event, selected_files)
        for item_def in self.app.setting.app.menu_items:
            if not item_def.is_visible:
                continue
            if item_def.type == "embedded" and item_def.name in id_command_map:
                menu.add_command(label=_(item_def.name), command=id_command_map[item_def.name])
            elif item_def.type == "custom":
                menu.add_command(label=item_def.name, command=lambda f=selected_files, m=item_def: self.__run_custom_command(f, m))
            elif item_def.type == "separator":
                menu.add_separator()
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
    
    def __run_custom_command(self, selected_files: list[Path], menu_item: MenuItemDef) -> None:
        @decorators.send_task
        def exec_custom_command(cmd_item: CustomMenuItem, test_mode: bool) -> None:
            def show_test_dialog(items) -> None:
                assert temp_dir is not None and clean_menu_item is not None
                dialog = TestResultDialog(self.app.view, items, clean_menu_item)
                dialog.file_tree.bind("<<TreeviewSelect>>", lambda _: dialog.show_result())
                dialog.file_tree.bind("<Double-Button-1>", lambda _: file_ops.open_file(dialog.file_tree.item(dialog.file_tree.selection()[0], "values")[1]))
                dialog.open_tempdir_btn.config(command=lambda: file_ops.open_file(str(temp_dir)))
                dialog.protocol("WM_DELETE_WINDOW", lambda: file_ops.rmtree(str(temp_dir)) or dialog.destroy())
                dialog.show_result()
            temp_dir = None
            work_files = selected_files
            if test_mode:
                temp_dir = Path(tempfile.mkdtemp(prefix="vimgfind_test_"))
                for i, f in enumerate(selected_files[:10]):
                    shutil.copy2(f, temp_dir / f"{i:02d}_{f.name}")
                work_files = [temp_dir / f"{i:02d}_{f.name}" for i, f in enumerate(selected_files)]

            exec_results = self.__exec_work_files(cmd_item, work_files)
            if test_mode:
                results = [TestResultItem(str(work_file), *res) for work_file, res in zip(work_files, exec_results)]
                self.app.view.after(0, show_test_dialog, results)
                return
            error_count = 0
            if menu_item.batch_mode:
                cmd, ret, out, err = exec_results[0]
                if ret != 0:
                    logging.error(f"执行命令：{cmd}, 命令输出：{out}, 错误原因：{err}")
                    error_count = len(selected_files)
            else:
                for tokens, ret, out, err in exec_results:
                    if ret != 0:
                        logging.error(f"执行命令失败：{tokens}, 错误原因：{err}")
                        error_count += 1
            if error_count == 0:
                self.app.search_controller.show_toast(_("{label}成功！", label=menu_item.name))
            else:
                self.app.search_controller.show_toast(_("{count}张图片的命令执行失败。", count=error_count))

        clean_menu_item = self.__resolve_test_item(menu_item)
        if clean_menu_item is None:
            return
        cmd_item = CustomMenuItem(clean_menu_item)
        if not cmd_item.resolve_ask():
            return
        exec_custom_command(cmd_item, clean_menu_item != menu_item)

    def __resolve_test_item(self, menu_item: MenuItemDef) -> MenuItemDef | None:
        lines = menu_item.command.strip().split('\n')
        test_mode = lines[0].strip() == "#test"
        if not test_mode:
            return menu_item

        clean = '\n'.join(lines[1:]).strip()
        if not clean:
            messagebox.showinfo(_("提示"), _("#test 模式已开启，但未输入实际命令。"))
            return None
        new_menu_item = copy.deepcopy(menu_item)
        new_menu_item.command = clean
        return new_menu_item

    @staticmethod
    def __exec_work_files(cmd_item: CustomMenuItem,  work_files: list[Path]) -> list[tuple[str, int, str, str]]:
        if cmd_item.menu_item.batch_mode:
            cmd = shlex.join(cmd_item.resolve(work_files))
            ret, out, err = file_ops.run_cmd(cmd)
            return [(cmd, ret, out, err)] * len(work_files)
        results = []
        for f in work_files:
            cmd = shlex.join(cmd_item.resolve([f]))
            ret, out, err = file_ops.run_cmd(cmd)
            results.append((cmd, ret, out, err))
        return results
