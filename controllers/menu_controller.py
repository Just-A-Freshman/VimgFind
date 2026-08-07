from __future__ import annotations

from pathlib import Path
from tkinter.font import Font
from tkinter import messagebox, filedialog
from typing import Callable, TYPE_CHECKING
import tkinter as tk
import logging
import tempfile
import shutil
import copy
import time

from ttkbootstrap import Menu

from config.settings import TkS, Setting, WinInfo
from config.types import MenuItemDef
from views.widgets import BasicImagePreviewView, PreviewCanvasView, simpledialog
from views.test_dialog import TestResultDialog, TestResultItem
from utils.i18n import _
import utils.shortcut as shortcut
import utils.file_ops as file_ops
import utils.image_ops as image_ops
import utils.decorators as decorators
import utils.cmd_parser as cmd_parser

if TYPE_CHECKING:
    from .app_controller import AppController


class MenuController:
    def __init__(self, app_controller: AppController) -> None:
        self.app = app_controller
        self.executor = CustomCommandExecutor(app_controller)
        self.__last_image_save_dir: Path | None = None
        # 双击打开校验。事件序列（macOS Tk + ToDesk 环境实测）：
        #   标准 Tk：第二次按下只产生 <Double-Button-1>（<Button-1> 不再触发）
        #   异常环境：第二次按下会同时产生 <Button-1> 和多个 <Double-Button-1>（重复分发）
        # 因此需要同时记录 prev/cur，并根据 Double 前是否紧邻 <Button-1> 选择参考点。
        self.__prev_click: tuple[object, str] | None = None
        self.__cur_click: tuple[object, str] | None = None
        self.__prev_click_time: float = 0.0
        self.__cur_click_time: float = 0.0
        self.__last_click_widget: object | None = None
        self.__last_click_time: float = 0.0
        self.__last_double_widget: object | None = None
        self.__last_double_time: float = 0.0
        # ── 临时诊断日志（复现“点击两个不同 item 触发打开”后请删除本段）──
        self.__diag_path = Setting.config_path / "dbl_diag.log"

    def __diag(self, *parts) -> None:
        try:
            with open(self.__diag_path, "a", encoding="utf-8") as f:
                f.write(time.strftime("%H:%M:%S") + " " + " | ".join(str(p) for p in parts) + "\n")
        except Exception:
            pass

    def on_item_single_click(self, event: tk.Event) -> None:
        try:
            item = event.widget.identify_item(event)
        except Exception:
            item = ""
        self.__prev_click = self.__cur_click
        self.__prev_click_time = self.__cur_click_time
        self.__cur_click = (event.widget, item)
        self.__cur_click_time = time.monotonic()
        self.__last_click_widget = event.widget
        self.__last_click_time = self.__cur_click_time
        self.__diag("Button-1", type(event.widget).__name__, f"x={event.x}", f"y={event.y}",
                    f"xr={event.x_root}", f"yr={event.y_root}", f"item={item}")

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
                self.embeded_command(event, paths).get(item.name, lambda: None)()
                if item.name in ["复制图片", "复制路径"]:
                    self.app.search_controller.show_toast(_("{label}成功！", label=item.name))
            else:
                self.executor.run(paths, item)
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
        menu_font = Font(font=adjustment_menu.cget("font"))
        menu_width = max(menu_font.measure(get_label(i)) for i in range(adjustment_menu.index(tk.END) or 0 + 1)) + TkS(65)
        adjustment_menu.post(winfo_right - menu_width, event.widget.winfo_rooty() + TkS(25))
        adjustment_menu.bind("<Unmap>", lambda e: adjustment_menu.destroy())

    def double_click_open_file(self, event: tk.Event) -> None:
        if not isinstance(event.widget, BasicImagePreviewView):
            return
        try:
            current_item = event.widget.identify_item(event)
        except Exception:
            current_item = ""
        now = time.monotonic()
        cur = self.__cur_click
        cur_same_widget = cur is not None and cur[0] is event.widget
        # ── 拦截迟到的重复 <Double-Button-1>（关键）──
        # 异常环境（ToDesk）下每次按压会重复分发多个 Double，且可能乱序到达：
        # 快速切换 item 时，前一次按压的 Double 可能在后一次按压的 <Button-1> 之后才到。
        # 若 Double 的 item 与最近一次 <Button-1>（cur）的 item 不符，说明它不是本次
        # 按压的双击信号，而是上一次按压迟到的重复事件 → 忽略。
        if current_item != "" and cur_same_widget and cur[1] != current_item:
            self.__diag("Double-Button-1", f"item={current_item}", f"cur_item={cur[1]}", "SKIP(stale-item)")
            return
        # ── 拦截同一次按压的重复 Double ──
        # 同 widget 上，上一次 Double 晚于最近一次 <Button-1>（两次 Double 之间无新按压）
        # → 同一按压的重复分发（实测 Double#1 后 111~209ms 的 Double#2/#3）→ 忽略。
        if (self.__last_double_widget is event.widget
                and self.__last_click_widget is event.widget
                and self.__last_double_time > self.__last_click_time):
            self.__diag("Double-Button-1", f"item={current_item}", "SKIP(duplicate)")
            return
        if current_item != "":
            self.__last_double_widget = event.widget
            self.__last_double_time = now
        if current_item == "":
            self.__diag("Double-Button-1", type(event.widget).__name__, f"x={event.x}", f"y={event.y}",
                        f"xr={event.x_root}", f"yr={event.y_root}", "item=''", "BLOCK(empty)")
            return
        # ── 选择参考点 ──
        # 若 Double 前 ~80ms 内刚有同 widget 的 <Button-1>（异常环境：第二次按下同时触发
        # <Button-1> 与 <Double-Button-1>，该 Button-1 已把 cur 更新为本次按下）→ 与更早的
        # prev（上一次按压）比对；否则（标准 Tk：第二次按下只产生 Double）→ 与 cur 比对。
        if (self.__last_click_widget is event.widget
                and now - self.__last_click_time <= 0.08):
            ref, ref_time = self.__prev_click, self.__prev_click_time
        else:
            ref, ref_time = cur, self.__cur_click_time
        if ref is None or ref[0] is not event.widget or ref[1] != current_item:
            self.__diag("Double-Button-1", type(event.widget).__name__, f"x={event.x}", f"y={event.y}",
                        f"xr={event.x_root}", f"yr={event.y_root}", f"item={current_item}",
                        f"ref={ref[1] if ref else None}", f"dt={now - ref_time:.3f}", "BLOCK(item-mismatch)")
            return
        # 间隔超过 0.5s（超出双击窗口）视为两次独立单击，不触发打开
        if now - ref_time > 0.5:
            self.__diag("Double-Button-1", f"item={current_item}", f"dt={now - ref_time:.3f}", "BLOCK(stale)")
            return
        selected_file = Path(event.widget.item(current_item)[0])
        if not selected_file.exists():
            self.__diag("Double-Button-1", f"item={current_item}", "OPEN-FAIL(not-exist)")
            messagebox.showinfo(_("提示"), _("文件不存在！"))
        else:
            self.__diag("Double-Button-1", f"item={current_item}", f"dt={now - ref_time:.3f}", "OPEN", str(selected_file))
            file_ops.open_file(selected_file)

    def save_as_image(self, *src_paths: Path) -> None:
        self.__last_image_save_dir = self.__last_image_save_dir or src_paths[0].parent 
        for src_path in src_paths:
            save_path = filedialog.asksaveasfilename(
                parent=self.app.view,
                filetypes=[(f"{i}(*{i})", f"*{i}") for i in Setting.accepted_exts if i not in [".psd"]],
                initialfile=file_ops.generate_copy_name(self.__last_image_save_dir / src_path.name).name,
                initialdir=self.__last_image_save_dir,
                defaultextension=src_path.suffix
            )
            if not save_path:
                break
            dest_path = Path(save_path)
            self.__last_image_save_dir = dest_path.parent
            image_ops.save_as_image(src_path, dest_path)
        
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

    def embeded_command(self, event: tk.Event, selected_files: list[Path]) -> dict[str, Callable]:
        return {
            "复制图片": lambda f=selected_files: file_ops.copy_files(*f),
            "复制路径": lambda f=selected_files: file_ops.copy_text(*f, tk=self.app.view),
            "图片另存为": lambda f=selected_files: self.save_as_image(*f),
            "删除图片": lambda f=selected_files: self.delete_files(event, f),
            "打开图片": lambda: file_ops.open_file(selected_files[0]),
            "打开文件夹": lambda: file_ops.open_file(selected_files[0], True)
        }
    
    def __create_context_menu(self, event: tk.Event, selected_files: list[Path]) -> Menu:
        menu = Menu(self.app.view, tearoff=0, activeborderwidth=TkS(3), bd=0)
        id_command_map = self.embeded_command(event, selected_files)
        for item_def in self.app.setting.app.menu_items:
            if not item_def.is_visible:
                continue
            if item_def.type == "embedded" and item_def.name in id_command_map:
                menu.add_command(label=_(item_def.name), command=id_command_map[item_def.name])
            elif item_def.type == "custom":
                menu.add_command(label=item_def.name, command=lambda f=selected_files, m=item_def: self.executor.run(f, m))
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
        default_count = (10, 50, 100)
        current_count = self.app.setting.app.max_match_count
        for count in default_count:
            label = _("结果数: {count}", count=count) + ("✓" if count == current_count else "")
            menu.add_command(label=label, command=lambda c=count: ctrl.set_preview_result_count(c))
        label = _("自定义数量") if current_count in default_count else _("自定义: {count}", count=current_count) + "✓"
        menu.add_command(label=label, command=lambda: ctrl.set_preview_result_count(simpledialog.askinteger(_("输入"), _("请输入不大于500的数字："))))

        menu.add_separator()
        menu.add_cascade(label=_("切换模型"), menu=model_menu)
        if self.app.index_controller.is_updating:
            model_menu.add_command(label=_("索引更新中，暂不可用"), state=tk.DISABLED)
            return menu
        for model in self.app.model_controller.get_downloaded_models():
            model_menu.add_command(
                label=(model.meta.name + "✓") if model.meta.id == self.app.setting.app.current_model else model.meta.name,
                command=lambda model=model: self.app.model_controller.switch_model(model.meta.id, resend_search=True),
            )
        return menu
    

class CustomCommandExecutor:
    def __init__(self, app_controller: AppController) -> None:
        self.app = app_controller

    def run(self, selected_files: list[Path], menu_item: MenuItemDef) -> None:
        clean_menu_item = self.__resolve_test_item(menu_item)
        if clean_menu_item is None:
            return
        test_mode = clean_menu_item != menu_item
        parse_result = cmd_parser.parse(clean_menu_item.command)
        if parse_result.errors:
            messagebox.showerror(_("命令语法错误"), "\n".join(f"{e.message}（第{e.line + test_mode}行，第{e.col}列）" for e in parse_result.errors))
            return
        ask_values = self.__collect_ask_values(parse_result.asks)
        if ask_values is None:
            return
        
        @decorators.send_task
        def exec_custom_command() -> None:
            temp_dir = None
            work_files = selected_files
            if test_mode:
                temp_dir = Path(tempfile.mkdtemp(prefix="vimgfind_test_"))
                for i, f in enumerate(selected_files[:10]):
                    shutil.copy2(f, temp_dir / f"{i:02d}_{f.name}")
                work_files = [temp_dir / f"{i:02d}_{f.name}" for i, f in enumerate(selected_files[:10])]

            # 执行结果展示 / 记录
            exec_results = self.__exec_work_files(clean_menu_item, work_files, ask_values, cwd=str(temp_dir) if temp_dir is not None else None)
            if test_mode:
                results = [TestResultItem(str(work_file), *res) for work_file, res in zip(work_files, exec_results)]
                self.app.view.after(0, self.__show_test_dialog, results, clean_menu_item, temp_dir)
                return
            
            error_count = 0
            if menu_item.batch_mode:
                cmd, ret, out, err, time_consuming = exec_results[0]
                if ret != 0:
                    logging.error(f"执行命令：{cmd}, 命令输出：{out}, 错误原因：{err}")
                    error_count = len(selected_files)
            else:
                for tokens, ret, out, err, time_consuming in exec_results:
                    if ret != 0:
                        logging.error(f"执行命令失败：{tokens}, 错误原因：{err}")
                        error_count += 1
            if error_count == 0:
                self.app.search_controller.show_toast(_("{label}成功！", label=menu_item.name))
            else:
                self.app.search_controller.show_toast(_("{count}张图片的命令执行失败。", count=error_count))
        
        exec_custom_command()

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

    def __collect_ask_values(self, asks: list[str]) -> dict[str, str | list[str]] | None:
        values: dict[str, str | list[str]] = {}
        for name in asks:
            val = self.__prompt_ask(name)
            if val is None:
                return None
            values[name] = val
        return values

    def __prompt_ask(self, var_name: str) -> str | list[str] | None:
        parent = self.app.view
        if var_name == 'ask_dir':
            v = filedialog.askdirectory(parent=parent, title=_("选择文件夹"))
            return v if v else None
        elif var_name == 'ask_file':
            v = filedialog.askopenfilename(parent=parent, title=_("选择文件"))
            return v if v else None
        elif var_name == 'ask_files':
            v = filedialog.askopenfilenames(parent=parent, title=_("选择文件"))
            return list(v) if v else None
        elif var_name == 'ask_string':
            return simpledialog.askstring(_("输入"), _("请输入文本："), parent=parent)
        elif var_name == 'ask_int':
            v = simpledialog.askinteger(_("输入"), _("请输入整数："), parent=parent)
            return str(v) if v is not None else None
        elif var_name == 'ask_float':
            v = simpledialog.askfloat(_("输入"), _("请输入数字："), parent=parent)
            return str(v) if v is not None else None
        return None

    @staticmethod
    def __exec_work_files(menu_item: MenuItemDef, work_files: list[Path], ask_values: dict[str, str | list[str]], cwd: str | None = None) -> list[tuple[list[str], int, str, str, float]]:
        def build_vars(paths: list[Path]) -> dict[str, str | list[str]]:
            first = paths[0]
            vars: dict[str, str | list[str]] = {
                "path": str(first),
                "paths": [str(p) for p in paths],
                "dir": str(first.parent),
                "name": first.name,
                "noext": first.stem,
                "ext": first.suffix,
                "count": str(len(paths)),
            }
            vars.update(ask_values)
            return vars

        if menu_item.batch_mode:
            cmd = cmd_parser.resolve(menu_item.command, build_vars(work_files))
            assert not cmd.errors and cmd.argv is not None
            start = time.perf_counter()
            ret, out, err = file_ops.run_cmd(cmd.argv, cwd=cwd if cwd is not None else str(work_files[0].parent))
            return [(cmd.argv, ret, out, err, time.perf_counter() - start)] * len(work_files)
        results = []
        for f in work_files:
            cmd = cmd_parser.resolve(menu_item.command, build_vars([f]))
            assert not cmd.errors and cmd.argv is not None
            start = time.perf_counter()
            ret, out, err = file_ops.run_cmd(cmd.argv, cwd=cwd if cwd is not None else str(f.parent))
            results.append((cmd.argv, ret, out, err, time.perf_counter() - start))
        return results

    def __show_test_dialog(self, items, clean_menu_item, temp_dir) -> None:
        assert temp_dir is not None and clean_menu_item is not None
        dialog = TestResultDialog(self.app.view, items, clean_menu_item)
        dialog.copy_btn.update_idletasks()
        dialog.copy_btn.bind("<ButtonRelease-1>", lambda e: dialog.copy_btn.config(text="✓") or dialog.after(1000, lambda: e.widget.config(text=_("复制"))))
        dialog.file_tree.bind("<<TreeviewSelect>>", lambda _: dialog.show_result())
        dialog.file_tree.bind("<Double-Button-1>", lambda _: file_ops.open_file(dialog.file_tree.item(dialog.file_tree.selection()[0], "values")[1]))
        dialog.open_tempdir_btn.config(command=lambda: file_ops.open_file(str(temp_dir)))
        dialog.copy_btn.config(command=lambda: file_ops.copy_text(dialog.detail_text.get("1.0", tk.END), tk=self.app.view))
        dialog.copy_btn.config(width=round(dialog.copy_btn.winfo_width() / Font(font=WinInfo.default_font).measure('0')))
        dialog.bind("<Destroy>", lambda e: e.widget is dialog and file_ops.rmtree(str(temp_dir)))
        dialog.show_result()
