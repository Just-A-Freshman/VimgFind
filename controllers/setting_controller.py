from __future__ import annotations

from pathlib import Path
from tkinter import filedialog, messagebox
from tkinter.font import nametofont
import tkinter as tk
from typing import Literal, Callable, TYPE_CHECKING
import threading

from .update_controller import UpdateController
from config.settings import Setting, WinInfo, TkS
from views import SettingDialog
from utils.i18n import I18n, _
import utils.shortcut as shortcut
import utils.file_ops as file_ops
import utils.shortcut as shortcut
import utils.update_checker as update_checker

if TYPE_CHECKING:
    from .app_controller import AppController
    from views import SettingDialog, GeneralTab, CustomMenuTab


class SettingController:
    def __init__(self, app_controller: AppController) -> None:
        self.app = app_controller
        self.dialog = None

    def change_theme(self, target_theme: str = "") -> None:
        style = self.app.view.style
        valid_theme_names = style.theme_names()
        self.app.setting.app.ui_style = target_theme if target_theme in valid_theme_names else "superhero"
        style.theme_use(self.app.setting.app.ui_style)
        style.configure("Search.TEntry", padding=(TkS(2), 0, TkS(27), 0))
        style.configure('TNotebook.Tab', font=(WinInfo.default_font_family, TkS(-18)))
        style.configure("sub.TNotebook")
        style.configure('sub.TNotebook.Tab', font=(WinInfo.default_font_family, WinInfo.default_font_size))
        style.configure("Treeview", rowheight=TkS(30))
        default_font = nametofont("TkDefaultFont")
        default_font.configure(family=WinInfo.default_font_family, size=WinInfo.default_font_size)
        self.app.view.search_tab.search_entry.config(style="Search.TEntry")
        self.app.view.search_tab.filter_btn.config(bg=style.colors.get("inputbg"), fg=style.colors.get("inputfg")) # type: ignore
        self.app.view.search_tab.nav_page_label.config(font=("", TkS(-18)))
        self.app.view.index_tab.index_tip_label.config(font=(WinInfo.default_font_family, TkS(-18)))
        self.app.view.model_tab.detail_desc_text.config(
            bg=style.colors.get('bg'), fg=style.colors.get('fg'),      # type: ignore
            selectbackground=style.colors.get('selectbg'),             # type: ignore
        )

    def show_dialog(self) -> None:
        def destroy():
            self.app.setting.save()
            if self.dialog is not None:
                self.dialog.destroy()
                self.dialog = None

        if self.dialog is not None:
            return
        self.dialog = SettingDialog(self.app.view)
        general_ctrl = GeneralController(self.dialog.general_tab, self.app)
        custom_menu_ctrl = CustomMenuController(self.dialog.custom_menu_tab, self.app)
        general_ctrl.env_init()
        custom_menu_ctrl.env_init()
        self.dialog.protocol("WM_DELETE_WINDOW", destroy)

    def on_inner_shortcut(self, event, shortcut_map: tuple[tuple[list[str], Callable], ...]) -> str | None:
        grab_shortcut = shortcut.build_shortcut(event)
        for inner_shortcut, command in shortcut_map:
            if grab_shortcut == inner_shortcut:
                command(event)
                break


class GeneralController:
    LOCALE_MAP = {"zh-CN": 0, "en-US": 1}
    REVERSE_LOCALE_MAP = {0: "zh-CN", 1: "en-US"}

    def __init__(self, general_tab: GeneralTab, app_controller: AppController) -> None:
        self.general_tab = general_tab
        self.app = app_controller

    def env_init(self) -> None:
        tab = self.general_tab
        for i in range(2):
            tab.maximize_checkbutton.invoke()
            tab.topmost_checkbutton.invoke()
        tab.theme_combobox.bind("<<ComboboxSelected>>", lambda _: self.app.setting_controller.change_theme(tab.theme_combobox.get()))
        tab.locale_combobox.bind("<<ComboboxSelected>>", self.__on_locale_change)
        tab.maximize_checkbutton.config(command=lambda: setattr(
            self.app.setting.app, "maximize_window",
            self.general_tab.maximize_checkbutton.instate(["selected"]))
        )
        tab.topmost_checkbutton.config(command=self.__on_topmost_change)
        tab.open_folder_btn.config(command=lambda: file_ops.open_file(self.app.setting.get_active_config_path().parent))
        tab.open_config_btn.config(command=lambda: file_ops.open_file(self.app.setting.get_active_config_path().absolute()))
        tab.change_config_btn.config(command=self.__change_config_path)
        tab.help_btn.config(command=lambda: None)
        tab.error_log_btn.config(command=lambda: file_ops.open_file(Setting.error_log))
        tab.check_update_btn.config(command=self.__check_update)
        idx = self.LOCALE_MAP.get(self.app.setting.app.locale, 0)
        tab.locale_combobox.current(idx)

        themes = sorted(self.app.view.style.theme_names())
        tab.theme_combobox.config(values=themes)
        current = self.app.setting.app.ui_style

        tab.theme_combobox.set(current if current in themes else themes[0])
        if self.app.setting.app.maximize_window:
            tab.maximize_checkbutton.invoke()
        if self.app.setting.app.topmost_window:
            tab.topmost_checkbutton.invoke()
        
        active_path = Setting.setting_path
        if self.app.setting.app.other_config_path:
            other = Path(self.app.setting.app.other_config_path)
            if other.exists() and other != Setting.setting_path:
                active_path = other
        tab.config_path_entry.config(state="normal")
        tab.config_path_entry.delete(0, "end")
        tab.config_path_entry.insert(0, str(active_path))
        tab.config_path_entry.config(state="readonly")

    def __on_locale_change(self, _event=None) -> None:
        idx = self.general_tab.locale_combobox.current()
        new_locale = self.REVERSE_LOCALE_MAP.get(idx, "zh-CN")
        if new_locale != self.app.setting.app.locale:
            self.app.setting.app.locale = new_locale
            I18n().load(new_locale)
            messagebox.showinfo(_("提示"), _("语言设置已更改，重启应用后完全生效。"),)

    def __on_topmost_change(self) -> None:
        if self.app.setting_controller.dialog is None:
            return
        is_topmost: bool = self.general_tab.topmost_checkbutton.instate(["selected"])
        self.app.setting.app.topmost_window = is_topmost
        self.app.view.attributes("-topmost", is_topmost)
        self.app.setting_controller.dialog.attributes("-topmost", is_topmost)

    def __change_config_path(self) -> None:
        path = filedialog.askopenfilename(
            title=_("选择配置文件"),
            filetypes=[(_("JSON 文件"), "*.json"), (_("所有文件"), "*.*")],
        )
        if not path:
            return
        messagebox.showinfo(_("提示"), _("配置文件已切换，需要重启后才能生效。"))
        self.app.setting.app.other_config_path = path
        self.app.destroy()

    def __check_update(self) -> None:
        def on_check_result(result: update_checker.UpdateCheckResult) -> None:
            if result.error:
                messagebox.showerror(_("检查更新失败"), result.error)
            elif not result.has_update:
                messagebox.showinfo(_("检查更新"), _(
                    "当前版本：v{current}\n你使用的已是最新版本！\n\n仓库地址：{repo}", 
                    current=result.current_version, repo=WinInfo.repo_url)
                )
            else:
                msg = _("发现新版本 v{latest}（当前版本 v{current}）\n\n是否下载更新？",
                        latest=result.latest_version, current=result.current_version)
                if messagebox.askyesno(_("发现新版本"), msg):
                    UpdateController(self.app).do_update(result.download_url, result.latest_version)
            self.general_tab.check_update_btn.config(state="normal", text=_("检查更新"))
        
        self.general_tab.check_update_btn.config(state="disabled", text=_("正在检查..."))
        def _check():
            result = update_checker.check()
            self.general_tab.after(0, lambda: on_check_result(result))

        threading.Thread(target=_check, daemon=True).start()


class CustomMenuController:
    DEFAULT_ITEM = {"label": _("未命名"), "is_visible": False, "batch_mode": False, "shortcut": [], "command": ""}

    def __init__(self, custom_menu_tab: CustomMenuTab, app_controller: AppController) -> None:
        self.custom_menu_tab = custom_menu_tab
        self.app = app_controller
        self.__items_data: dict[str, dict] = {}

    def env_init(self) -> None:
        tab = self.custom_menu_tab
        for item in self.app.setting.app.custom_menu_items:
            full_item = {**self.DEFAULT_ITEM, **item}
            iid = self.custom_menu_tab.custom_menu_tree.insert("", tk.END, values=(
                full_item["label"], _("是") if full_item["is_visible"] else _("否"),
            ))
            self.__items_data[iid] = full_item
        for i in range(2):
            tab.is_visible_checkbutton.invoke()
            tab.batch_mode_checkbutton.invoke()
        tab.add_button.config(command=self.__add_menu_item)
        tab.delete_button.config(command=self.__delete_menu_item)
        tab.custom_menu_tree.bind("<<TreeviewSelect>>", lambda _: self.__on_tree_select())
        tab.name_edit_entry.bind("<KeyRelease>", lambda _: self.__sync_item_property("label"))
        tab.is_visible_checkbutton.config(command=lambda: self.__sync_item_property("is_visible"))
        tab.batch_mode_checkbutton.config(command=lambda: self.__sync_item_property("batch_mode"))
        tab.shortcut_entry.bind("<FocusIn>", lambda e: shortcut.reset_modifiers(), add="+")
        tab.shortcut_entry.bind("<KeyPress>", shortcut.track_modifiers, add="+")
        tab.shortcut_entry.bind("<KeyRelease>", shortcut.track_modifiers, add="+")
        tab.shortcut_entry.bind("<KeyPress>", lambda e: shortcut.on_shortcut_key(
            e, tab.shortcut_entry, lambda _: self.__sync_item_property("shortcut")), add="+"
        )
        tab.shortcut_entry.unbind("<Enter>")
        tab.shortcut_entry.bind("<FocusOut>", lambda e: tab.shortcut_warning_tooltip.hide_tip(), add="+")
        tab.command_text.bind("<KeyRelease>", lambda _: self.__sync_item_property("command"))
        tab.bind("<Destroy>", lambda _: self.__save_item_data())
        self.__save_item_data(schedule=True)
        self.__on_tree_select()

    def __on_tree_select(self) -> None:
        selection = self.custom_menu_tab.custom_menu_tree.selection()
        if not selection:
            self.custom_menu_tab.show_default()
            return
        iid = selection[0]
        item = self.__items_data.get(iid)
        if item:
            self.custom_menu_tab.show_detail(**item)

    def __add_menu_item(self) -> None:
        tab = self.custom_menu_tab
        for iid, item in self.__items_data.items():
            item["label"] = item["label"] or self.DEFAULT_ITEM["label"]
            if item == self.DEFAULT_ITEM:
                tab.custom_menu_tree.selection_set(iid)
                tab.custom_menu_tree.focus(iid)
                tab.show_detail(**item)
                return

        new_item = self.DEFAULT_ITEM.copy()
        iid = tab.custom_menu_tree.insert("", tk.END, values=(new_item["label"], _("否")))
        self.__items_data[iid] = new_item
        tab.custom_menu_tree.selection_set(iid)
        tab.custom_menu_tree.focus(iid)
        tab.show_detail(**new_item)

    def __delete_menu_item(self) -> None:
        selection = self.custom_menu_tab.custom_menu_tree.selection()
        if not selection:
            return
        if not messagebox.askyesno(_("删除"), _("确定要删除选中的菜单项吗？")):
            return
        self.custom_menu_tab.custom_menu_tree.delete(*selection)
        for iid in selection:
            self.__items_data.pop(iid, None)
        self.custom_menu_tab.show_default()

    def __sync_item_property(self, property: Literal["label", "is_visible", "batch_mode", "shortcut", "command"]):
        selection = self.custom_menu_tab.custom_menu_tree.selection()
        if not selection:
            return
        tab = self.custom_menu_tab
        iid = selection[0]
        if iid not in self.__items_data:
            return
        if property == "label":
            self.__items_data[iid]["label"] = tab.name_edit_entry.get().strip()
            tab.custom_menu_tree.set(iid, column="#1", value=self.__items_data[iid]["label"])
        elif property == "is_visible":
            self.__items_data[iid]["is_visible"] = tab.is_visible_checkbutton.instate(["selected"])
            tab.custom_menu_tree.set(
                iid, column="#2", value=_("是") if self.__items_data[iid]["is_visible"] else _("否")
            )
        elif property == "batch_mode":
            self.__items_data[iid]["batch_mode"] = tab.batch_mode_checkbutton.instate(["selected"])
        elif property == "shortcut":
            tab.shortcut_warning_tooltip.hide_tip()
            grab_shortcut = [s.strip() for s in tab.shortcut_entry.get().split("＋") if s.strip()]
            has_registered = [i["shortcut"] for i in self.__items_data.values()]
            if grab_shortcut in shortcut.INNER_SHORTCUT:
                tab.shortcut_warning_tooltip.text = _("内置快捷键，无法占用。")
                tab.shortcut_warning_tooltip.show_tip()
            elif grab_shortcut not in [self.__items_data[iid]["shortcut"], [], ["??"]] and grab_shortcut in has_registered:
                tab.shortcut_warning_tooltip.text = _("该快键键已被你注册过。")
                tab.shortcut_warning_tooltip.show_tip()
            self.__items_data[iid]["shortcut"] = grab_shortcut
        else:
            self.__items_data[iid]["command"] = tab.command_text.get("1.0", tk.END).strip()
        
    def __save_item_data(self, schedule: bool = False) -> None:
        self.app.setting.app.custom_menu_items = list(self.__items_data.values())
        if schedule:
            self.custom_menu_tab.after(3000, self.__save_item_data, schedule)

