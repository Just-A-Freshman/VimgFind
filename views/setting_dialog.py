from __future__ import annotations

import tkinter as tk

from ttkbootstrap.constants import LINK
from ttkbootstrap import Button, Frame, Label, Combobox, Checkbutton, Entry, Labelframe, Treeview, Scrollbar, Notebook, Text, tooltip

from config.settings import WinInfo, TkS
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
        update_tab = UpdateTab(notebook)
        notebook.add(general_tab, text=_("  常规  "))
        notebook.add(custom_menu_tab, text=_("  自定义菜单  "))
        notebook.add(update_tab, text=_("  更新  "))
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
    __slots__ = (
        "locale_combobox", "theme_combobox",
        "maximize_checkbutton", "topmost_checkbutton",
        "config_path_entry", "open_folder_btn",
        "open_config_btn", "change_config_btn",
        "help_btn", "error_log_btn",
    )

    def __init__(self, parent) -> None:
        super().__init__(parent)
        self.grid_columnconfigure(0, weight=1)
        self.locale_combobox = self.__set_locale_combobox()
        self.theme_combobox = self.__set_theme_combobox()
        self.maximize_checkbutton, self.topmost_checkbutton = self.__set_maximize_topmost_checkbutton()
        config_label_frame = self.__set_config_labelframe()
        self.config_path_entry = self.__set_config_path_entry(config_label_frame)
        self.open_folder_btn, self.open_config_btn, self.change_config_btn = self.__set_config_buttons(config_label_frame)
        self.help_btn, self.error_log_btn = self.__set_bottom_buttons()

    def __set_locale_combobox(self) -> Combobox:
        frame = Frame(self)
        frame.grid(row=0, column=0, padx=TkS(10), pady=TkS(12), sticky=tk.W)
        Label(frame, text=_("显示语言：")).pack(side=tk.LEFT)
        locale_combobox = Combobox(
            frame, values=["中文", "English"], state="readonly", width=TkS(6), 
            font=(WinInfo.default_font_family, WinInfo.default_font_size),
        )
        locale_combobox.pack(side=tk.LEFT)
        return locale_combobox
    
    def __set_theme_combobox(self) -> Combobox:
        frame = Frame(self)
        frame.grid(row=1, column=0, padx=TkS(10), pady=TkS(12), sticky=tk.W)
        Label(frame, text=_("主题设置：")).pack(side=tk.LEFT)
        theme_combobox = Combobox(
            frame, state="readonly", width=TkS(6), style="info",
            font=(WinInfo.default_font_family, WinInfo.default_font_size),
        )
        theme_combobox.pack(side=tk.LEFT)
        return theme_combobox
    
    def __set_maximize_topmost_checkbutton(self) -> tuple[Checkbutton, Checkbutton]:
        checkbutton_frame = Frame(self)
        checkbutton_frame.grid(row=2, column=0, padx=TkS(10), pady=TkS(15), columnspan=4, sticky=tk.EW)
        maximize_checkbutton = Checkbutton(checkbutton_frame, text=_("启动时最大化窗口"))
        topmost_checkbutton = Checkbutton(checkbutton_frame, text=_("将当前窗口置顶"))
        maximize_checkbutton.pack(side=tk.LEFT)
        topmost_checkbutton.pack(side=tk.LEFT, padx=TkS(10))
        return maximize_checkbutton, topmost_checkbutton
    
    def __set_config_labelframe(self):
        config_labelframe = Labelframe(self, text=_("配置文件存储位置"))
        config_labelframe.grid(row=3, column=0, padx=TkS(10), pady=TkS(15), columnspan=8, sticky=tk.EW)
        return config_labelframe

    def __set_config_path_entry(self, parent):
        config_path_entry = Entry(parent, state="readonly", font=(WinInfo.default_font_family, TkS(-12)))
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

    def __set_bottom_buttons(self) -> tuple[Button, Button]:
        bottom_frame = Frame(self)
        bottom_frame.grid(row=4, column=0, sticky=tk.EW, padx=TkS(10))
        help_btn = Button(bottom_frame, text=_("帮助文档"), style=LINK, cursor="hand2", takefocus=False)
        error_log_btn = Button(bottom_frame, text=_("错误日志"), style=LINK, cursor="hand2", takefocus=False)
        help_btn.pack(side=tk.LEFT)
        error_log_btn.pack(side=tk.RIGHT)
        return help_btn, error_log_btn


class CustomMenuTab(Frame):
    add_button: Button
    delete_button: Button
    custom_menu_tree: Treeview
    in_use_checkbutton: Checkbutton
    shortcut_tip_label: Label
    shortcut_entry: Entry
    command_tip_label: Label
    command_text: Text
    name_edit_tip_label: Label
    name_edit_entry: Entry
    command_variable_tip = _(
        "命令将在命令行中执行，有以下变量可用：\n"
        "$image_path\t图像路径\n"
        "$image_dir\t图像所在文件夹路径\n"
        "$filename\t图像的名称（带后缀）\n"
        "$basename\t图像的名称（无后缀）\n"
        "$ext\t\t图像的后缀名"
    )
    __slots__ = (
        "add_button", "delete_button",
        "custom_menu_tree", "help_btn",
        "batch_mode_checkbutton", "in_use_checkbutton",
        "shortcut_entry", "command_text",
        "shortcut_tip_label", "command_tip_label",
        "name_edit_tip_label", "name_edit_entry",
    )

    def __init__(self, parent) -> None:
        super().__init__(parent)
        left_frame, right_frame = self.__set_column_frames()
        self.add_button, self.delete_button = self.__set_menu_buttons(left_frame)
        self.custom_menu_tree = self.__set_custom_menu_tree(left_frame)
        self.help_btn, edit_frame = self.__set_help_edit_frame(right_frame)
        self.name_edit_tip_label = Label(edit_frame)
        self.name_edit_entry = Entry(edit_frame, font=(WinInfo.default_font_family, WinInfo.default_font_size))
        self.in_use_checkbutton = Checkbutton(edit_frame, text=_("启用"))
        self.batch_mode_checkbutton = Checkbutton(edit_frame, text=_("批量模式"))
        self.shortcut_tip_label = Label(edit_frame, text=_("快捷键："))
        self.shortcut_entry = Entry(edit_frame, font=(WinInfo.default_font_family, WinInfo.default_font_size))
        self.command_tip_label = Label(edit_frame, text=_("执行命令："))
        self.command_tooltip = tooltip.ToolTip(self.command_tip_label, topmost=True, text=CustomMenuTab.command_variable_tip)
        self.command_text = Text(edit_frame)
        self.show_default()

    def __set_column_frames(self) -> tuple[Frame, Frame]:
        left_frame = Frame(self)
        left_frame.place(relx=0, rely=0, relheight=1, relwidth=0.5)
        right_frame = Frame(self)
        right_frame.place(relx=0.51, rely=0, relheight=1, relwidth=0.48)
        return left_frame, right_frame
    
    def __set_menu_buttons(self, parent: Frame) -> tuple[Button, Button]:
        btn_frame = Frame(parent)
        btn_frame.pack(fill=tk.X, padx=TkS(3), pady=(TkS(10), 0))
        add_btn = Button(btn_frame, text=_("新建"), takefocus=False, cursor="hand2")
        add_btn.pack(side=tk.LEFT, padx=(0, TkS(5)), ipadx=TkS(10))
        del_btn = Button(btn_frame, text=_("删除"), takefocus=False, cursor="hand2")
        del_btn.pack(side=tk.LEFT, ipadx=TkS(10))
        return add_btn, del_btn

    def __set_custom_menu_tree(self, parent: Frame) -> Treeview:
        columns = {_("菜单名称"): TkS(80), _("是否启用"): TkS(80)}
        treeview = Treeview(parent, show="headings", columns=list(columns), padding=TkS(1))
        for text, width in columns.items():
            treeview.heading(text, text=text, anchor=tk.CENTER)
            treeview.column(text, anchor=tk.CENTER, width=width, stretch=True)

        scroll = Scrollbar(treeview, orient=tk.VERTICAL, command=treeview.yview)
        scroll.pack(fill=tk.Y, side=tk.RIGHT, padx=TkS(1), pady=TkS(1))
        treeview.configure(yscrollcommand=scroll.set)
        treeview.pack(fill=tk.BOTH, expand=True, pady=TkS(5))
        return treeview
    
    def __set_help_edit_frame(self, parent) -> tuple[Button, Labelframe]:
        help_btn = Button(parent, text=_("帮助文档"), takefocus=False, cursor="hand2", style="link")
        help_btn.pack(side=tk.TOP, anchor=tk.E, pady=(TkS(5), 0))
        edit_frame = Labelframe(parent, text=_("配置编辑"))
        edit_frame.pack(fill=tk.BOTH, expand=True, pady=(TkS(1), TkS(5)))
        edit_frame.grid_rowconfigure(3, weight=1)
        edit_frame.grid_columnconfigure(1, weight=1)
        return help_btn, edit_frame

    def show_detail(self, name: str, in_use: bool, batch_mode: bool, shortcut: list[str], command: str) -> None:
        self.name_edit_tip_label.config(text=_("名称："))
        self.name_edit_tip_label.grid(row=0, column=0, padx=TkS(5), sticky=tk.W)
        self.name_edit_entry.grid(row=0, column=1, sticky=tk.EW, padx=(0, TkS(5)))
        self.name_edit_entry.delete(0, tk.END)
        self.name_edit_entry.insert(tk.END, name)
        self.in_use_checkbutton.grid(row=0, column=2, sticky=tk.W, padx=TkS(5))
        if in_use: self.in_use_checkbutton.invoke()
        self.shortcut_tip_label.grid(row=1, column=0, padx=TkS(5), pady=TkS(10), sticky=tk.W)
        self.shortcut_entry.grid(row=1, column=1, sticky=tk.EW, columnspan=2, padx=(0, TkS(5)))
        self.shortcut_entry.delete(0, tk.END)
        self.shortcut_entry.insert(tk.END, " + ".join(shortcut))
        self.command_tip_label.grid(row=2, column=0, padx=TkS(5), columnspan=2, sticky=tk.W)
        self.batch_mode_checkbutton.grid(row=2, column=1, columnspan=2, sticky=tk.E, padx=TkS(5))
        self.command_text.grid(row=3, column=0, sticky=tk.NSEW, columnspan=3, padx=TkS(5), pady=(0, TkS(5)))
        if batch_mode: self.batch_mode_checkbutton.invoke()
        self.command_text.delete('1.0', tk.END)
        self.command_text.insert(tk.END, command)

    def show_default(self) -> None:
        for w in self.name_edit_tip_label.master.children.values():
            w.grid_forget()
        self.name_edit_tip_label.config(text=_("选择菜单配置详细信息"))
        self.name_edit_tip_label.grid(row=3, column=1, padx=TkS(20))


class UpdateTab(Frame):
    pass

