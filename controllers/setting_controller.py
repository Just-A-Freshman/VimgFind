from __future__ import annotations

import os
from pathlib import Path
from tkinter import filedialog, messagebox
from tkinter.font import nametofont
import tkinter as tk
from typing import TYPE_CHECKING

from config.settings import Setting, WinInfo, TkS
from views import SettingDialog
from utils.i18n import I18n, _
import utils.decorators as decorators
import utils.update_checker as update_checker

if TYPE_CHECKING:
    from .app_controller import AppController
    from views import SettingDialog, GeneralTab, CustomMenuTab, UpdateTab


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

    def show_dialog(self):
        def destroy():
            custom_menu_ctrl.save_edits()
            self.app.setting.save()
            if self.dialog is not None:
                self.dialog.destroy()
                self.dialog = None

        self.dialog = SettingDialog(self.app.view)
        general_ctrl = GeneralController(self.dialog.general_tab, self.app)
        custom_menu_ctrl = CustomMenuController(self.dialog.custom_menu_tab, self.app)
        # self.update_ctrl = UpdateController(dialog, self.app)
        # dialog.general_tab.topmost_checkbutton.bind("<Button-1>", lambda _: dialog.lift())
        self.dialog.protocol("WM_DELETE_WINDOW", destroy)


class GeneralController:
    LOCALE_MAP = {"zh-CN": 0, "en-US": 1}
    REVERSE_LOCALE_MAP = {0: "zh-CN", 1: "en-US"}

    def __init__(self, general_tab: GeneralTab, app_controller: AppController) -> None:
        self.general_tab = general_tab
        self.app = app_controller
        self.__bind_event()
        self.__env_init()

    def __bind_event(self) -> None:
        tab = self.general_tab
        tab.theme_combobox.bind("<<ComboboxSelected>>", lambda _: self.app.setting_controller.change_theme(tab.theme_combobox.get()))
        tab.locale_combobox.bind("<<ComboboxSelected>>", self.__on_locale_change)
        tab.maximize_checkbutton.config(command=lambda: setattr(
            self.app.setting.app, "maximize_window",
            self.general_tab.maximize_checkbutton.instate(["selected"]))
        )
        tab.topmost_checkbutton.config(command=self.__on_topmost_change)
        tab.open_folder_btn.config(command=lambda: os.startfile(self.__get_active_config_path().parent))
        tab.open_config_btn.config(command=lambda: os.startfile(self.__get_active_config_path()))
        tab.change_config_btn.config(command=self.__change_config_path)
        tab.help_btn.config(command=lambda: None)
        tab.reset_btn.config(command=self.__reset_to_default)

    def __env_init(self) -> None:
        tab = self.general_tab
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
        self.app.setting.app.other_config_path = path
        new_app = self.app.setting.load_app_config()
        self.app.setting._app = new_app
        self.__env_init()
        messagebox.showinfo(
            _("提示"),
            _("配置文件已切换，部分设置可能需要重启应用后完全生效。"),
        )

    def __get_active_config_path(self) -> Path:
        if self.app.setting.app.other_config_path:
            other = Path(self.app.setting.app.other_config_path)
            if other.exists() and other != Setting.setting_path:
                return other
        return Setting.setting_path

    def __reset_to_default(self) -> None:
        if not messagebox.askyesno(_("恢复默认"), _("确定要将所有设置恢复为默认值吗？\n此操作需要重启应用。")):
            return
        self.app.setting._app = self.app.setting.load_app_config(default=True)
        self.app.setting.save()
        self.app.view.after(100, self.app.destroy)


class CustomMenuController:
    MODIFIER_KEYS: dict[str, str] = {
        "Control_L": "Ctrl", "Control_R": "Ctrl",
        "Shift_L": "Shift", "Shift_R": "Shift",
        "Alt_L": "Alt", "Alt_R": "Alt",
        "Super_L": "Win", "Super_R": "Win",
    }
    SPECIAL_KEYS: dict[str, str] = {
        "Return": "Enter",
        "space": "Space",
        "Tab": "Tab",
        "Escape": "Esc",
        "BackSpace": "Backspace",
        "Delete": "Delete",
        "Home": "Home",
        "End": "End",
        "Prior": "Page Up",
        "Next": "Page Down",
        "Insert": "Insert",
        "Print": "Print Screen",
        "Pause": "Pause",
        "Up": "↑",
        "Down": "↓",
        "Left": "←",
        "Right": "→",
    }
    DEFAULT_ITEM = {"label": _("未命名"), "in_use": False, "shortcut": [], "command": ""}

    def __init__(self, custom_menu_tab: CustomMenuTab, app_controller: AppController) -> None:
        self.custom_menu_tab = custom_menu_tab
        self.app = app_controller
        self.__items_data: dict[str, dict] = {}
        self.__env_init()
        self.__bind_event()
        if not custom_menu_tab.custom_menu_tree.selection():
            custom_menu_tab.show_default()

    def __bind_event(self):
        self.custom_menu_tab.add_button.config(command=self.__add_menu_item)
        self.custom_menu_tab.delete_button.config(command=self.__delete_menu_item)
        self.custom_menu_tab.custom_menu_tree.bind("<<TreeviewSelect>>", self.__on_tree_select)
        self.custom_menu_tab.name_edit_entry.bind("<KeyRelease>", self.__on_name_change)
        self.custom_menu_tab.in_use_checkbutton.config(command=self.__on_in_use_change)
        self.custom_menu_tab.shortcut_entry.bind("<KeyPress>", self.__on_shortcut_key)
        self.custom_menu_tab.shortcut_entry.bind("<FocusOut>", self.__on_shortcut_focusout)
        self.custom_menu_tab.command_text.bind("<KeyRelease>", self.__on_command_change)

    def __env_init(self) -> None:
        for item in self.app.setting.app.custom_menu_items:
            full_item = {**self.DEFAULT_ITEM, **item}
            iid = self.custom_menu_tab.custom_menu_tree.insert("", tk.END, values=(
                full_item["label"], _("是") if full_item["in_use"] else _("否"),
            ))
            self.__items_data[iid] = full_item
    
    def __save_shortcut_to_data(self, shortcut: list[str]) -> None:
        tab = self.custom_menu_tab
        selection = tab.custom_menu_tree.selection()
        if not selection:
            return
        iid = selection[0]
        item = self.__items_data.get(iid)
        if item is not None:
            item["shortcut"] = shortcut
            self.__items_data[iid] = item

    @property
    def item_data(self):
        return self.__items_data
    
    def __on_shortcut_key(self, event) -> str | None:
        tab = self.custom_menu_tab
        keysym: str = event.keysym
        if keysym in CustomMenuController.MODIFIER_KEYS:
            return "break"

        if keysym in ("BackSpace", "Delete"):
            if not bool(event.state & (0x0004 | 0x0001 | 0x0008 | 0x0040)):
                tab.shortcut_entry.delete(0, "end")
                self.__save_shortcut_to_data([])
                return "break"

        modifiers: list[str] = []
        if event.state & 0x0004:
            modifiers.append("Ctrl")
        if event.state & 0x0001:
            modifiers.append("Shift")
        if event.state & 0x0008:
            modifiers.append("Alt")
        if event.state & 0x0040:
            modifiers.append("Win")

        key_name: str = CustomMenuController.SPECIAL_KEYS.get(keysym, keysym)
        if len(key_name) == 1 and key_name.isalpha():
            key_name = key_name.lower()

        shortcut = modifiers + [key_name]
        tab.shortcut_entry.delete(0, "end")
        tab.shortcut_entry.insert(0, " + ".join(shortcut))

        self.__save_shortcut_to_data(shortcut)

        return "break"

    def __on_shortcut_focusout(self, _event=None) -> None:
        selection = self.custom_menu_tab.custom_menu_tree.selection()
        if not selection:
            return
        iid = selection[0]
        item = self.__items_data.get(iid)
        if item is None:
            return
        raw = self.custom_menu_tab.shortcut_entry.get()
        item["shortcut"] = [s.strip() for s in raw.split("+") if s.strip()]
        self.__items_data[iid] = item

    def __on_command_change(self, _event=None) -> None:
        selection = self.custom_menu_tab.custom_menu_tree.selection()
        if not selection:
            return
        iid = selection[0]
        item = self.__items_data.get(iid)
        if item is None:
            return
        item["command"] = self.custom_menu_tab.command_text.get("1.0", "end-1c")
        self.__items_data[iid] = item

    def __on_name_change(self, _event=None) -> None:
        selection = self.custom_menu_tab.custom_menu_tree.selection()
        if not selection:
            return
        iid = selection[0]
        item = self.__items_data.get(iid)
        if item is None:
            return
        item["label"] = self.custom_menu_tab.name_edit_entry.get()
        self.__items_data[iid] = item
        self.custom_menu_tab.custom_menu_tree.item(
            iid, values=(item["label"], _("是") if item["in_use"] else _("否")),
        )

    def __on_in_use_change(self) -> None:
        selection = self.custom_menu_tab.custom_menu_tree.selection()
        if not selection:
            return
        iid = selection[0]
        item = self.__items_data.get(iid)
        if item is None:
            return
        item["in_use"] = bool(self.custom_menu_tab.in_use_checkbutton.instate(["selected"]))
        self.__items_data[iid] = item
        self.custom_menu_tab.custom_menu_tree.item(
            iid, values=(item["label"], _("是") if item["in_use"] else _("否")),
        )

    def __on_tree_select(self, _event=None) -> None:
        selection = self.custom_menu_tab.custom_menu_tree.selection()
        if not selection:
            self.custom_menu_tab.show_default()
            return
        iid = selection[0]
        item = self.__items_data.get(iid)
        if item:
            self.custom_menu_tab.show_detail(item["label"], item["in_use"], item["shortcut"], item["command"])

    def __add_menu_item(self) -> None:
        tab = self.custom_menu_tab
        self.save_edits()
        for iid, item in self.__items_data.items():
            label = item.get("label", "")
            if (
                (label == "" or label == self.DEFAULT_ITEM["label"])
                and not item.get("in_use", False)
                and not item.get("shortcut")
                and not item.get("command")
            ):
                tab.custom_menu_tree.selection_set(iid)
                tab.custom_menu_tree.focus(iid)
                tab.show_detail(item["label"], item["in_use"], item["shortcut"], item["command"])
                return

        new_item = dict(self.DEFAULT_ITEM)
        iid = tab.custom_menu_tree.insert("", tk.END, values=(new_item["label"], _("否")),)
        self.__items_data[iid] = new_item
        tab.custom_menu_tree.selection_set(iid)
        tab.custom_menu_tree.focus(iid)
        tab.show_detail(new_item["label"], new_item["in_use"], new_item["shortcut"], new_item["command"])

    def __delete_menu_item(self) -> None:
        selection = self.custom_menu_tab.custom_menu_tree.selection()
        if not selection:
            return
        if not messagebox.askyesno(_("删除"), _("确定要删除选中的菜单项吗？")):
            return
        iid = selection[0]
        self.custom_menu_tab.custom_menu_tree.delete(iid)
        self.__items_data.pop(iid, None)
        self.custom_menu_tab.show_default()

    def save_edits(self) -> None:
        tab = self.custom_menu_tab
        selection = tab.custom_menu_tree.selection()
        if not selection:
            return
        iid = selection[0]
        item = self.__items_data.get(iid)
        if item is None:
            return
        item["label"] = tab.name_edit_entry.get()
        item["in_use"] = bool(tab.in_use_checkbutton.instate(["selected"]))
        raw = tab.shortcut_entry.get()
        item["shortcut"] = [s.strip() for s in raw.split("+") if s.strip()]
        item["command"] = tab.command_text.get("1.0", "end-1c")
        self.__items_data[iid] = item
        self.app.setting.app.custom_menu_items = list(self.item_data.values())


class UpdateController:
    pass
    # def open_setting_dialog(self) -> None:
    #     @decorators.send_task
    #     def check_for_update() -> None:
    #         result = update_checker.check()
    #         if result.error is not None:
    #             messagebox.showerror(
    #                 _("检查更新失败"),
    #                 _("无法检查更新：{error}\n\n请检查网络连接后重试。", error=result.error),
    #             )
    #             return
    #         if result.has_update:
    #             answer = messagebox.askyesno(
    #                 _("检查更新"),
    #                 _("发现新版本：v{version}\n是否立即更新？", version=result.latest_version),
    #             )
    #             if not answer:
    #                 return
    #             from .update_controller import UpdateController
    #             dialog.destroy()
    #             update_ctrl = UpdateController(self.app)
    #             self.app.view.after(0, lambda: update_ctrl.do_update(result.download_url, result.latest_version))
    #         else:
    #             messagebox.showinfo(
    #                 _("检查更新"),
    #                 _("当前版本：v{version}\n你使用的已是最新版本！\n\n仓库地址：{url}",
    #                   version=WinInfo.version, url=WinInfo.repo_url),
    #             )

    #     dialog = SettingDialog(self.app.view)
    #     self.general_ctrl = GeneralController(dialog, self.app)
    #     self.custom_menu_ctrl = CustomMenuController(dialog, self.app)
    #     dialog.protocol("WM_DELETE_WINDOW", lambda: self._on_close_setting(dialog))

