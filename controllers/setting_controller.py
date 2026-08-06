from __future__ import annotations

from pathlib import Path
from typing import Literal, Callable, TYPE_CHECKING
from tkinter import filedialog, messagebox
from tkinter.font import nametofont
import tkinter as tk

from ttkbootstrap.style import Colors

from config.settings import Setting, WinInfo, TkS
from config.types import MenuItemDef
from .update_controller import UpdateController, UpdateCheckResult
from views import SettingDialog
from utils.i18n import I18n, _
import utils.shortcut as shortcut
import utils.file_ops as file_ops
import utils.decorators as decorators

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
        colors: Colors = style.colors   # type:ignore
        style.configure('TNotebook.Tab', font=(WinInfo.default_font[0], 13))
        style.configure("sub.TNotebook")
        style.configure('sub.TNotebook.Tab', font=WinInfo.default_font)
        style.configure("TEntry", padding=TkS(2.5))
        style.configure("TCombobox", padding=TkS(2.5))
        style.configure("TButton", padding=(TkS(5), TkS(2.5)))
        style.configure("Link.TButton", padding=(TkS(5), TkS(2.5)))
        style.configure("Search.TEntry", padding=(TkS(2), 0, TkS(27), 0))
        style.configure("Treeview", rowheight=TkS(30))
        style.configure("NoBorder.Treeview", borderwidth=0, relief=tk.FLAT)
        style.configure('inner.Link.TButton', background=colors.get("inputbg"), borderwidth=0, foreground=colors.get("info"))
        style.map('TNotebook.Tab', padding=[('selected', (TkS(3), TkS(2.5))), ('!selected', (TkS(3), TkS(2.5)))])
        style.map('sub.TNotebook.Tab', padding=[('selected', (TkS(3), TkS(2.5))), ('!selected', (TkS(3), TkS(2.5)))])
        style.map('inner.Link.TButton', background=[('active', colors.get("bg") if colors.hex_to_rgb(colors.get("bg")) != colors.hex_to_rgb(colors.get("inputbg")) else colors.get("active"))])   # type:ignore
        default_font = nametofont("TkDefaultFont")
        default_font.configure(family=WinInfo.default_font[0], size=WinInfo.default_font[1])
        self.app.view.search_tab.search_entry.config(style="Search.TEntry")
        self.app.view.search_tab.filter_btn.config(bg=colors.get("inputbg"), fg=colors.get("inputfg"))   # type: ignore
        self.app.view.search_tab.nav_page_label.config(font=(WinInfo.default_font[0], 13))
        self.app.view.index_tab.index_tip_label.config(font=(WinInfo.default_font[0], 13))
        self.app.view.model_tab.detail_desc_text.config(bg=colors.get("bg"), fg=colors.get("fg"), selectbackground=colors.get('selectbg'))   # type:ignore

    def show_dialog(self) -> None:
        def destroy():
            self.app.setting.save()
            if self.dialog is not None:
                custom_menu_ctrl.save_item_data()
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
    def __init__(self, general_tab: GeneralTab, app_controller: AppController) -> None:
        self.general_tab = general_tab
        self.app = app_controller
        locales = I18n.available_locales()
        self.LOCALE_MAP: dict[str, int] = {loc: i for i, loc in enumerate(locales)}
        self.REVERSE_LOCALE_MAP: dict[int, str] = {i: loc for i, loc in enumerate(locales)}

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
        tab.help_btn.config(command=lambda: self.app.setting.link_to_docs())
        tab.error_log_btn.config(command=lambda: file_ops.open_file(Setting.error_log))
        tab.check_update_btn.config(command=self.__check_update)
        tab.locale_combobox.config(values=[I18n.locale_name(loc) for loc in I18n.available_locales()])
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

    @decorators.send_task
    def __check_update(self) -> None:
        def on_check_result(result: UpdateCheckResult) -> None:
            if result.error:
                messagebox.showerror(_("检查更新失败"), result.error)
            elif not result.has_update:
                info = _("当前版本：v{current}\n你使用的已是最新版本！\n\n仓库地址：{repo}", current=WinInfo.version, repo=WinInfo.repo_url)
                messagebox.showinfo(_("检查更新"), info)
            else:
                info = _("发现新版本 v{latest}（当前版本 v{current}）\n\n是否下载更新？", latest=result.latest_version, current=WinInfo.version)
                if messagebox.askyesno(_("发现新版本"), info):
                    update_controller.do_update(result.download_url, result.latest_version)
            try:
                self.general_tab.check_update_btn.config(state="normal", text=_("检查更新"))
            except tk.TclError:
                pass
        
        self.general_tab.check_update_btn.config(state="disabled", text=_("正在检查..."))
        update_controller = UpdateController(self.app)
        result = update_controller.check()
        self.general_tab.after(0, lambda: on_check_result(result))


class CustomMenuController:
    def __init__(self, custom_menu_tab: CustomMenuTab, app_controller: AppController) -> None:
        self.custom_menu_tab = custom_menu_tab
        self.app = app_controller
        self.__items_data: dict[str, MenuItemDef] = {}

    def env_init(self) -> None:
        tab = self.custom_menu_tab
        for item in self.app.setting.app.menu_items:
            text = item.name if item.type != "embedded" else _(item.name)
            iid = self.custom_menu_tab.custom_menu_tree.insert("", tk.END, text=text, checked=item.is_visible)
            self.__items_data[iid] = item
        for i in range(2):
            tab.batch_mode_checkbutton.invoke()
        tab.add_button.config(command=self.__add_menu_item)
        tab.add_sep_btn.config(command=lambda: self.__add_menu_item(default=MenuItemDef(name="——————————", type="separator")))
        tab.delete_button.config(command=self.__delete_menu_item)
        tab.help_btn.config(command=lambda: self.app.setting.link_to_docs(_("自定义菜单命令")))
        tab.custom_menu_tree.config(on_toggle=lambda iid, checked: setattr(self.__items_data.get(iid), "is_visible", checked))
        tab.custom_menu_tree.bind("<<TreeviewSelect>>", lambda _: self.__on_tree_select(), add="+")
        tab.name_edit_entry.bind("<KeyRelease>", lambda _: self.__sync_item_property("name"))
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
        tab.state_show_btn.config(command=lambda: self.__toggle_test_mode(tab))
        self.save_item_data(schedule=True)
        self.__on_tree_select()

    def __on_tree_select(self) -> None:
        selection = self.custom_menu_tab.custom_menu_tree.selection()
        if not selection:
            self.custom_menu_tab.show_default()
            return
        iid = selection[0]
        item = self.__items_data.get(iid)
        if item:
            self.custom_menu_tab.show_detail(item)

    def __add_menu_item(self, default: MenuItemDef | None = None) -> None:
        if default is None:
            default = MenuItemDef()
        tab = self.custom_menu_tab
        for iid, item in self.__items_data.items():
            item.name = item.name or default.name
            if item == default:
                tab.custom_menu_tree.selection_set(iid)
                tab.custom_menu_tree.focus(iid)
                tab.show_detail(item)
                tab.custom_menu_tree.see(iid)
                return

        new_item = default
        iid = tab.custom_menu_tree.insert("", tk.END, text=new_item.name, checked=False)
        self.__items_data[iid] = new_item
        tab.custom_menu_tree.selection_set(iid)
        tab.custom_menu_tree.focus(iid)
        tab.show_detail(new_item)
        tab.custom_menu_tree.see(iid)

    def __delete_menu_item(self) -> None:
        selection = self.custom_menu_tab.custom_menu_tree.selection()
        if not selection:
            return
        for iid in selection:
            if self.__items_data[iid].type == "embedded":
                messagebox.showwarning(_("提示"), _("内置菜单项无法删除"))
                return
        if not messagebox.askyesno(_("删除"), _("确定要删除选中的菜单项吗？")):
            return
        self.custom_menu_tab.custom_menu_tree.delete(*selection)
        for iid in selection:
            self.__items_data.pop(iid, None)
        self.custom_menu_tab.show_default()

    def __sync_item_property(self, property: Literal["name", "batch_mode", "shortcut", "command"]):
        selection = self.custom_menu_tab.custom_menu_tree.selection()
        if not selection:
            return
        tab = self.custom_menu_tab
        iid = selection[0]
        menu_item = self.__items_data[iid]
        if (menu_item.type == "embedded" and property != "shortcut") or (menu_item.type == "separator" and property != "is_visible"):
            return
        if property == "name":
            self.__items_data[iid].name = tab.name_edit_entry.get().strip()
            tab.custom_menu_tree.item(iid, text=self.__items_data[iid].name)
        elif property == "batch_mode":
            self.__items_data[iid].batch_mode = tab.batch_mode_checkbutton.instate(["selected"])
        elif property == "shortcut":
            tab.shortcut_warning_tooltip.hide_tip()
            grab_shortcut = [s.strip() for s in tab.shortcut_entry.get().split("＋") if s.strip()]
            has_registered = [i.shortcut for i in self.__items_data.values()]
            if grab_shortcut in shortcut.INNER_SHORTCUT:
                tab.shortcut_warning_tooltip.text = _("内置快捷键，无法占用。")
                tab.shortcut_warning_tooltip.show_tip()
            elif grab_shortcut not in [menu_item.shortcut, [], ["??"]] and grab_shortcut in has_registered:
                tab.shortcut_warning_tooltip.text = _("该快键键已被你注册过。")
                tab.shortcut_warning_tooltip.show_tip()
            self.__items_data[iid].shortcut = grab_shortcut
        else:
            self.__items_data[iid].command = tab.command_text.get("1.0", tk.END).strip()
            tab.state_show_btn.config(text=_("◍测试") if tab.command_text.get("1.0", "1.0 lineend").strip() == "#test" else _("●正常"))

    def __toggle_test_mode(self, tab: CustomMenuTab) -> None:
        first_line = tab.command_text.get("1.0", "1.0 lineend").strip()
        if first_line == "#test":
            tab.command_text.delete("1.0", "2.0")
            if tab.command_text.get("1.0", "1.0 lineend").strip() == "":
                tab.command_text.delete("1.0", "2.0")
        else:
            tab.command_text.insert("1.0", "#test\n")
        self.__sync_item_property("command")

    def save_item_data(self, schedule: bool = False) -> None:
        self.app.setting.app.menu_items = [
            self.__items_data[k] for k in self.custom_menu_tab.custom_menu_tree.get_children("")
        ]
        if schedule:
            self.custom_menu_tab.after(1000, self.save_item_data, schedule)

