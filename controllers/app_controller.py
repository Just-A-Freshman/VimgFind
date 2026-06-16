from tkinter import messagebox
from ttkbootstrap import Style
from tkinterdnd2 import DND_FILES
import tkinter as tk
import webbrowser

from views import WinGUI, ExcludeDialog
from settings import Setting, WinInfo
from utils import FileOperation, Decorator
from core import SearchTool

from .filter_controller import FilterController
from .search_controller import SearchController
from .index_controller import IndexController
from .menu_controller import MenuController



class AppController:
    def __init__(self) -> None:
        self.view = WinGUI()
        self.setting = Setting()
        self.search_tools: SearchTool | None = None

        self.filter_controller = FilterController(self)
        self.search_controller = SearchController(self)
        self.index_controller = IndexController(self)
        self.menu_controller = MenuController(self)

        self.__change_theme(setting_theme=True)
        self.search_controller.set_preview_mode(
            self.setting.get_config("function", "preview_mode")
        )
        self.search_controller.set_similarity_threshold(
            self.setting.get_config("function", "similarity_threshold")
        )
        self.bind_event(first_time=True)
        self.view.after(0, self._delayed_init)
        self.view.protocol("WM_DELETE_WINDOW", self.destroy)

    def bind_event(self, first_time=False) -> None:
        tab = self.view.search_tab
        setting_tab = self.view.setting_tab

        tab.preview_view.bind("<<ItemviewSelect>>", self.search_controller.preview_found_image)
        tab.preview_view.bind("<Control-a>", lambda e: tab.preview_view.selection_set(tk.ALL))
        tab.preview_view.bind("<Control-v>", lambda e: self.search_controller.search_image_by_clipboard())
        preview_widgets = (tab.preview_canvas1, tab.preview_canvas2, tab.preview_view)
        for w in preview_widgets:
            w.bind("<Button-3>", lambda e, w=w: self.menu_controller.create_right_click_menu(e, w))
            w.bind("<Double-Button-1>", lambda e, w=w: self.menu_controller.double_click_open_file(e, w))

        if not first_time:
            return

        tab.search_by_browser_btn.config(command=self.search_controller.search_by_browser)
        tab.search_by_clipboard_btn.config(command=self.search_controller.search_image_by_clipboard)
        tab.search_entry.bind("<Return>", lambda e: self.search_controller.search_image_by_text())
        tab.more_options_button.config(command=self.menu_controller.create_preview_setting_menu)
        tab.filter_btn.bind("<Button-1>", lambda e: self.filter_controller.toggle_filter_panel())
        tab.filter_panel.confirm_btn.config(command=self.filter_controller.confirm_filter)
        tab.filter_panel.cancel_btn.config(command=self.filter_controller.cancel_filter)
        self.view.bind_all("<Button-1>", self.filter_controller.on_root_click, "+")
        self.filter_controller.init_filter_panel()

        setting_tab.index_dataset_table.bind("<Double-Button-1>", self.menu_controller.double_click_open_file)
        setting_tab.index_dataset_table.bind("<ButtonPress-1>", self.index_controller.drag_start, add="+")
        setting_tab.index_dataset_table.bind("<B1-Motion>", self.index_controller.drag_motion, add="+")
        setting_tab.index_dataset_table.bind("<ButtonRelease-1>", self.index_controller.drag_end, add="+")

        setting_tab.add_index_button.config(command=self.index_controller.add_search_dir)
        setting_tab.exclude_button.config(command=self.__open_exclude_dialog)
        setting_tab.clean_excluded_button.config(command=self.index_controller.clean_excluded)
        setting_tab.update_index_button.config(command=self.index_controller.sync_index)
        setting_tab.delete_index_button.config(command=self.index_controller.delete_search_dir)
        setting_tab.rebuild_index_button.config(command=self.index_controller.rebuild_index)

        setting_tab.theme_combobox.bind("<<ComboboxSelected>>", lambda e: self.__change_theme())
        setting_tab.open_setting_file_button.config(
            command=lambda: FileOperation.open_file(Setting.config_path)
        )
        setting_tab.open_repertory_button.config(command=self.__check_for_update)

        self.view.drop_target_register(DND_FILES)
        self.view.dnd_bind('<<Drop>>', self.__on_drop)

    def _delayed_init(self) -> None:
        self.search_tools = SearchTool(self.setting)
        self.__env_init()

    @Decorator.send_task
    def __env_init(self) -> None:
        setting_tab = self.view.setting_tab
        self.index_controller.refresh_index_dataset_table()
        setting_tab.update_threads_count_scale.set(
            value=self.setting.get_config("function", "max_work_thread")
        )
        if self.setting.get_config("function", "auto_update_index"):
            setting_tab.auto_update_btn.invoke()
            self.index_controller.sync_index(show_message=False)
        else:
            self.index_controller.update_index_tip()
        self.view.after(self.setting.schedule_save_interval, self.__schedule_save)

    def __change_theme(self, setting_theme=False) -> None:
        style = Style()
        setting_tab = self.view.setting_tab
        if setting_theme:
            valid_theme_names = style.theme_names()
            valid_theme_name = self.setting.get_config("function", "ui_style")
            valid_theme_name = valid_theme_name if valid_theme_name in valid_theme_names else "superhero"
            setting_tab.theme_combobox.current(valid_theme_names.index(valid_theme_name))
        theme_cbo_value = setting_tab.theme_combobox.get()
        setting_tab.theme_combobox.selection_clear()
        style.theme_use(theme_cbo_value)
        style.configure('TNotebook.Tab', font=('微软雅黑', 12))
        style.configure("Treeview", rowheight=50)
        self.filter_controller._sync_filter_btn_style()

    def __on_drop(self, event) -> None:
        file_paths_str: str = getattr(event, "data")
        file_paths = FileOperation.extract_file_paths(file_paths_str)
        tab_id = self.view.switch_tab.index(self.view.switch_tab.select())
        if tab_id == 0:
            self.search_controller.search_by_browser(file_paths[0])
        elif tab_id == 1:
            for dir_path in file_paths:
                self.index_controller.add_search_dir(dir_path)

    def __open_exclude_dialog(self) -> None:
        ExcludeDialog(self.view, self.setting)

    def __schedule_save(self) -> None:
        if self.search_tools:
            self.search_tools.save_index()
        self.view.after(self.setting.schedule_save_interval, self.__schedule_save)

    def destroy(self) -> None:
        try:
            setting_tab = self.view.setting_tab
            search_tab = self.view.search_tab
            self.setting.modity_config("function", "ui_style", setting_tab.theme_combobox.get())
            self.setting.modity_config("function", "auto_update_index", setting_tab.auto_update_btn.instate(['selected']))
            self.setting.modity_config("function", "max_work_thread", int(float(setting_tab.update_threads_count_scale.get())))
            self.setting.modity_config("function", "similarity_threshold", int(float(search_tab.filter_panel.sim_scale.get())))
            self.setting.save_settings()
            self.setting.clean_log()
            if self.search_tools:
                self.search_tools.destroy()
                self.search_tools.save_index()
            FileOperation.clear_folder_all(Setting.temp_image_path)
            if self.search_tools:
                self.search_tools.set_force_end_update(True)
        except Exception as e:
            messagebox.showerror("错误", str(e))
        finally:
            self.view.destroy()

    @Decorator.send_task
    def __check_for_update(self) -> None:
        from utils import UpdateChecker

        result = UpdateChecker.check()
        if result.error is not None:
            messagebox.showerror(
                "检查更新失败",
                f"无法检查更新：{result.error}\n\n请检查网络连接后重试。"
            )
            return

        if result.has_update:
            self._show_update_dialog(result)
        else:
            messagebox.showinfo(
                "检查更新",
                f"当前版本：v{WinInfo.version}\n"
                f"你使用的已是最新版本！\n\n"
                f"仓库地址：{WinInfo.repo_url}"
            )

    def _show_update_dialog(self, result) -> None:
        dialog = tk.Toplevel(self.view)
        dialog.title("发现新版本")
        win_width, win_height = 520, 480
        x = (self.view.winfo_screenwidth() - win_width) // 2
        y = (self.view.winfo_screenheight() - win_height) // 2
        dialog.geometry(f"{win_width}x{win_height}+{x}+{y}")
        dialog.minsize(480, 380)
        dialog.grab_set()

        bottom_frame = tk.Frame(dialog)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=15, pady=(10, 18))

        link_label = tk.Label(
            bottom_frame,
            text="下载增量更新包",
            fg="#0078D4",
            cursor="hand2",
            font=("微软雅黑", 10, "underline"),
        )
        link_label.pack(side=tk.LEFT)
        link_label.bind("<Button-1>", lambda e: (webbrowser.open(result.download_url), dialog.destroy()))

        close_btn = tk.Button(bottom_frame, text="关闭", command=dialog.destroy, padx=15, cursor="hand2")
        close_btn.pack(side=tk.RIGHT)

        header_frame = tk.Frame(dialog)
        header_frame.pack(fill=tk.X, padx=15, pady=(15, 5))
        tk.Label(
            header_frame,
            text=f"发现新版本: v{result.latest_version}",
            font=("微软雅黑", 13, "bold"),
            anchor=tk.W,
        ).pack(anchor=tk.W)
        tk.Label(
            header_frame,
            text=f"当前版本: v{result.current_version}",
            font=("微软雅黑", 10),
            fg="gray",
            anchor=tk.W,
        ).pack(anchor=tk.W)

        tk.Frame(dialog, height=2, bd=1, relief=tk.SUNKEN).pack(fill=tk.X, padx=15, pady=5)

        notes_label = tk.Label(dialog, text="更新内容:", anchor=tk.W, font=("微软雅黑", 10))
        notes_label.pack(fill=tk.X, padx=15, pady=(5, 2))

        text_frame = tk.Frame(dialog)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 5))

        text = tk.Text(text_frame, wrap=tk.WORD, font=("微软雅黑", 9))
        scrollbar = tk.Scrollbar(text_frame, orient=tk.VERTICAL, command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)
        body = result.release_body or "暂无更新说明"
        text.insert(tk.END, body)
        text.config(state=tk.DISABLED)
        text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
