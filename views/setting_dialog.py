from __future__ import annotations

import tkinter as tk
from tkinter.font import Font

from ttkbootstrap import Button, Frame, Label, Combobox, Checkbutton, Entry, Labelframe, Notebook, Text
from ttkbootstrap.widgets import ToolTip

from config.settings import WinInfo, TkS
from config.types import MenuItemDef
from .widgets import CheckboxTreeview
from utils.i18n import _


class SettingDialog(tk.Toplevel):
    general_tab: GeneralTab
    custom_menu_tab: CustomMenuTab
    _instance = None
    __slots__ = ("general_tab", "custom_menu_tab", "_initialized")

    def __new__(cls, parent=None):
        if cls._instance is not None and cls._instance.winfo_exists():
            cls._instance.lift()
            cls._instance.focus_force()
            return cls._instance
        instance = super().__new__(cls)
        cls._instance = instance
        return instance

    def __init__(self, parent) -> None:
        if hasattr(self, '_initialized'):
            return
        super().__init__(parent)
        self.withdraw()
        self._initialized = True
        self.general_tab, self.custom_menu_tab = self.__set_notebook()
        self.__win(parent)
        
    def __win(self, parent) -> None:
        self.transient(parent)
        self.update_idletasks()
        win_w = TkS(450)
        win_h = TkS(320)
        x = parent.winfo_rootx() + (parent.winfo_width() - win_w) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - win_h) // 2
        self.geometry(f"{win_w}x{win_h}+{x}+{y}")
        self.title(_("设置"))
        self.iconbitmap(WinInfo.ico_path)
        self.deiconify()

    def __set_notebook(self) -> tuple[GeneralTab, CustomMenuTab]:
        notebook = Notebook(self, style="sub.TNotebook")
        general_tab = GeneralTab(notebook)
        custom_menu_tab = CustomMenuTab(notebook)
        notebook.add(general_tab, text=_("  常规  "))
        notebook.add(custom_menu_tab, text=_("  自定义菜单  "))
        notebook.pack(fill=tk.BOTH, expand=True, padx=TkS(5), pady=TkS(5))
        return general_tab, custom_menu_tab


class GeneralTab(Frame):
    locale_combobox: Combobox
    theme_combobox: Combobox
    maximize_checkbutton: Checkbutton
    topmost_checkbutton: Checkbutton
    config_path_entry: Entry
    open_folder_btn: Button
    open_config_btn: Button
    change_config_btn: Button
    help_btn: Button
    error_log_btn: Button
    check_update_btn: Button
    __slots__ = (
        "locale_combobox", "theme_combobox",
        "maximize_checkbutton", "topmost_checkbutton",
        "config_path_entry", "open_folder_btn",
        "open_config_btn", "change_config_btn",
        "help_btn", "error_log_btn", "check_update_btn",
    )

    def __init__(self, parent) -> None:
        super().__init__(parent)
        self.grid_columnconfigure(0, weight=1)
        self.locale_combobox, self.theme_combobox = self.__set_locale_theme_combobox()
        self.maximize_checkbutton, self.topmost_checkbutton = self.__set_maximize_topmost_checkbutton()
        config_label_frame = self.__set_config_labelframe()
        self.config_path_entry = self.__set_config_path_entry(config_label_frame)
        self.open_folder_btn, self.open_config_btn, self.change_config_btn = self.__set_config_buttons(config_label_frame)
        self.help_btn, self.error_log_btn, self.check_update_btn = self.__set_bottom_buttons()

    def __set_locale_theme_combobox(self) -> tuple[Combobox, Combobox]:
        frame = Frame(self)
        frame.grid(row=0, column=0, padx=TkS(15), sticky=tk.W)
        Label(frame, text=_("显示语言：")).grid(row=0, column=0, sticky=tk.W)
        Label(frame, text=_("主题设置：")).grid(row=1, column=0, sticky=tk.W)
        locale_combobox = Combobox(frame, state="readonly")
        theme_combobox = Combobox(frame, state="readonly")
        locale_combobox.grid(row=0, column=1, pady=TkS(12))
        theme_combobox.grid(row=1, column=1, pady=TkS(12))
        return locale_combobox, theme_combobox
    
    def __set_maximize_topmost_checkbutton(self) -> tuple[Checkbutton, Checkbutton]:
        checkbutton_frame = Frame(self)
        checkbutton_frame.grid(row=2, column=0, padx=TkS(15), pady=TkS(15), columnspan=4, sticky=tk.EW)
        maximize_checkbutton = Checkbutton(checkbutton_frame, text=_("启动时最大化窗口"), cursor="hand2")
        topmost_checkbutton = Checkbutton(checkbutton_frame, text=_("将当前窗口置顶"), cursor="hand2")
        maximize_checkbutton.pack(side=tk.LEFT)
        topmost_checkbutton.pack(side=tk.LEFT, padx=TkS(15))
        return maximize_checkbutton, topmost_checkbutton
    
    def __set_config_labelframe(self):
        config_labelframe = Labelframe(self, text=_("配置文件存储位置"))
        config_labelframe.grid(row=3, column=0, padx=TkS(10), pady=(TkS(15), 0), columnspan=8, sticky=tk.EW)
        return config_labelframe

    def __set_config_path_entry(self, parent):
        config_path_entry = Entry(parent, state="readonly", font=(WinInfo.default_font[0], 9))
        config_path_entry.pack(side=tk.TOP, fill=tk.X, expand=True, padx=TkS(5), ipady=TkS(4))
        return config_path_entry

    def __set_config_buttons(self, parent) -> tuple[Button, Button, Button]:
        open_folder_btn = Button(parent, text=_("打开所在文件夹"), cursor="hand2", style="link", takefocus=False)
        open_config_btn = Button(parent, text=_("打开"), cursor="hand2", style="link", takefocus=False)
        change_config_btn = Button(parent, text=_("更改"), cursor="hand2", style="link", takefocus=False)
        open_folder_btn.pack(side=tk.LEFT, pady=TkS(3))
        change_config_btn.pack(side=tk.RIGHT, pady=TkS(3))
        open_config_btn.pack(side=tk.RIGHT, padx=(0, TkS(4)), pady=TkS(3))
        return open_folder_btn, open_config_btn, change_config_btn

    def __set_bottom_buttons(self) -> tuple[Button, Button, Button]:
        bottom_frame = Frame(self)
        bottom_frame.grid(row=4, column=0, sticky=tk.EW, padx=TkS(10), pady=TkS(10))
        help_btn = Button(bottom_frame, text=_("帮助文档"), style="link", cursor="hand2", takefocus=False)
        error_log_btn = Button(bottom_frame, text=_("错误日志"), style="link", cursor="hand2", takefocus=False)
        check_update_btn = Button(bottom_frame, text=_("检查更新"), style="link", cursor="hand2", takefocus=False)
        help_btn.pack(side=tk.LEFT)
        error_log_btn.pack(side=tk.LEFT)
        check_update_btn.pack(side=tk.RIGHT)
        return help_btn, error_log_btn, check_update_btn


class CustomMenuTab(Frame):
    add_button: Button
    add_sep_btn: Button
    delete_button: Button
    custom_menu_tree: CheckboxTreeview
    shortcut_tip_label: Label
    shortcut_entry: Entry
    command_tip_label: Label
    command_text: Text
    name_edit_tip_label: Label
    name_edit_entry: Entry
    __slots__ = (
        "add_button", "add_sep_btn", "delete_button",
        "custom_menu_tree", "help_btn",
        "batch_mode_checkbutton", "name_edit_tip_label", "name_edit_entry",
        "shortcut_tip_label", "shortcut_entry", "shortcut_warning_tooltip", 
        "command_tip_label", "command_text", "command_tooltip", "state_show_btn"
    )

    def __init__(self, parent) -> None:
        super().__init__(parent)
        left_frame, right_frame = self.__set_column_frames()
        self.add_button, self.add_sep_btn, self.delete_button = self.__set_menu_buttons(left_frame)
        self.custom_menu_tree = self.__set_custom_menu_tree(left_frame)
        self.help_btn, self.edit_frame = self.__set_help_edit_frame(right_frame)
        self.name_edit_tip_label = Label(self.edit_frame)
        self.name_edit_entry = Entry(self.edit_frame)
        self.batch_mode_checkbutton = Checkbutton(self.edit_frame, text=_("批量模式"), cursor="hand2")
        self.shortcut_tip_label = Label(self.edit_frame, text=_("快捷键："))
        self.shortcut_entry = Entry(self.edit_frame)
        self.shortcut_warning_tooltip = ToolTip(self.shortcut_entry, topmost=True)
        self.command_tip_label = Label(self.edit_frame, justify=tk.CENTER, wraplength=TkS(180), anchor=tk.CENTER)
        self.command_tooltip = ToolTip(self.command_tip_label, topmost=True, text="")
        self.command_text = Text(self.edit_frame, undo=True)
        self.state_show_btn = Button(self.command_text, style="inner.Link.TButton", takefocus=False, cursor="hand2")
        self.show_default()

    def __set_column_frames(self) -> tuple[Frame, Frame]:
        left_frame = Frame(self)
        left_frame.place(relx=0, rely=0, relheight=1, relwidth=0.5)
        right_frame = Frame(self)
        right_frame.place(relx=0.51, rely=0, relheight=1, relwidth=0.48)
        return left_frame, right_frame

    def __set_menu_buttons(self, parent: Frame) -> tuple[Button, Button, Button]:
        btn_frame = Frame(parent)
        btn_frame.pack(fill=tk.X, padx=TkS(0.5), pady=(TkS(10), 0))
        add_btn = Button(btn_frame, text=_("新建"), takefocus=False, cursor="hand2")
        add_sep_btn = Button(btn_frame, text=_("分隔线"), takefocus=False, cursor="hand2")
        del_btn = Button(btn_frame, text=_("删除"), takefocus=False, cursor="hand2")
        buttons = (add_btn, add_sep_btn, del_btn)
        font = Font(font=WinInfo.default_font)
        for i, btn in enumerate(buttons):
            btn_frame.grid_columnconfigure(i, weight=font.measure(btn["text"]) + 2 * TkS(12))
            btn.grid(row=0, column=i, sticky=tk.EW, padx=(0, TkS(5)) if i < len(buttons) - 1 else 0, ipadx=TkS(12))
        return add_btn, add_sep_btn, del_btn

    def __set_custom_menu_tree(self, parent: Frame) -> CheckboxTreeview:
        treeview = CheckboxTreeview(parent, checkbox_name=_("显示"), padding=TkS(1))
        treeview.heading("#0", text=_("菜单名称"), anchor=tk.CENTER)
        treeview.column("#0", anchor=tk.CENTER, width=TkS(160), stretch=True)
        treeview.pack(fill=tk.BOTH, expand=True, pady=TkS(5))
        return treeview

    def __set_help_edit_frame(self, parent) -> tuple[Button, Labelframe]:
        help_btn = Button(parent, text=_("帮助文档"), takefocus=False, cursor="hand2", style="link")
        help_btn.pack(side=tk.TOP, anchor=tk.E, pady=(TkS(5), 0))
        edit_frame = Labelframe(parent, text=_("配置编辑"))
        edit_frame.pack(fill=tk.BOTH, expand=True, pady=(TkS(1), TkS(5)))
        edit_frame.columnconfigure(1, weight=1)
        return help_btn, edit_frame

    def __reset_edit_layout(self) -> None:
        for row in range(4):
            self.edit_frame.rowconfigure(row, weight=0)
        for widget in self.edit_frame.children.values():
            widget.grid_forget()
        self.state_show_btn.place_forget()

    def show_detail(self, menu_item: MenuItemDef) -> None:
        self.__reset_edit_layout()
        if menu_item.type == "separator":
            self.command_tip_label.config(text=_("这是一条分隔线"))
            self.command_tip_label.grid(row=0, column=0, columnspan=2, sticky=tk.NSEW)
            self.edit_frame.rowconfigure(0, weight=1)
            self.command_tooltip.text = _("分隔线：用于从视觉上分离不同类型的菜单项")
            return

        self.name_edit_tip_label.config(text=_("名称："))
        self.name_edit_tip_label.grid(row=0, column=0, padx=TkS(5), sticky=tk.W)
        self.name_edit_entry.grid(row=0, column=1, sticky=tk.EW, padx=(0, TkS(5)))
        self.name_edit_entry.config(state=tk.NORMAL, cursor="xterm")
        self.name_edit_entry.delete(0, tk.END)
        self.name_edit_entry.insert(tk.END, menu_item.name if menu_item.type != "embedded" else _(menu_item.name))
        self.shortcut_tip_label.grid(row=1, column=0, padx=TkS(5), pady=(0, TkS(3)), sticky=tk.W)
        self.shortcut_entry.grid(row=1, column=1, sticky=tk.EW, padx=(0, TkS(5)), pady=TkS(5))
        self.shortcut_entry.delete(0, tk.END)
        self.shortcut_entry.insert(tk.END, " + ".join(menu_item.shortcut))

        if menu_item.type == "embedded":
            self.name_edit_entry.config(state="readonly")
            self.command_tip_label.config(text=_("这是一个内置菜单项"))
            self.command_tip_label.grid(row=2, column=0, columnspan=2, sticky=tk.NSEW)
            self.edit_frame.rowconfigure(2, weight=1)
            self.command_tooltip.text = _("内置菜单，无法修改它的名称或执行的命令。")
        else:
            self.command_tip_label.config(text=_("执行命令："))
            self.command_tip_label.grid(row=2, column=0, columnspan=2, padx=TkS(5), pady=TkS(4), sticky=tk.W)
            self.batch_mode_checkbutton.grid(row=2, column=1, sticky=tk.E, padx=TkS(5))
            self.command_text.grid(row=3, column=0, columnspan=2, sticky=tk.NSEW, padx=TkS(5), pady=(0, TkS(5)))
            self.edit_frame.rowconfigure(3, weight=1)
            if menu_item.batch_mode != self.batch_mode_checkbutton.instate(["selected"]):
                self.batch_mode_checkbutton.invoke()
            self.command_text.delete('1.0', tk.END)
            self.command_text.insert(tk.END, menu_item.command)
            self.command_tooltip.text = _((
                "可用变量列表：\n"
                "{path}\t选中图片的完整路径\n"
                "{dir}\t图片所在文件夹\n"
                "{name}\t完整文件名\n"
                "{noext}\t文件名无后缀\n"
                "{ext}\t后缀名，含点\n"
                "{paths}\t批量模式下的多图列表\n"
                "{count}\t批量模式下选中图片的数量\n"
                "{ask_?}\tstring,int,float,dir,file,files"
            ))
            self.state_show_btn.config(text=_("◍测试") if self.command_text.get("1.0", "1.0 lineend").strip() == "#test" else _("●正常"))
            self.state_show_btn.place(relx=1.0, rely=1.0, anchor=tk.SE)

    def show_default(self) -> None:
        self.__reset_edit_layout()
        self.command_tip_label.config(text=_("选择菜单进行配置"))
        self.command_tooltip.text = _("默认提示信息")
        self.command_tip_label.grid(row=0, column=0, columnspan=2, sticky=tk.NSEW)
        self.edit_frame.rowconfigure(0, weight=1)
