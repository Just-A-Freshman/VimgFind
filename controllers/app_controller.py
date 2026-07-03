from tkinter import messagebox
from tkinter.font import nametofont
from ttkbootstrap import Style
from tkinterdnd2 import DND_FILES
import tkinter as tk

from views import WinGUI, SettingDialog
from settings import Setting, WinInfo
import utils.file_ops as file_ops
import utils.decorators as decorators
import utils.update_checker as update_checker

from core import SearchTool
from .filter_controller import FilterController
from .search_controller import SearchController
from .index_controller import IndexController
from .menu_controller import MenuController
from .model_controller import ModelController



class AppController:
    def __init__(self) -> None:
        self.setting = Setting()
        self.view = WinGUI(self.setting.app.maximize_window)
        self.search_tools: SearchTool | None = None
        self.filter_controller = FilterController(self)
        self.search_controller = SearchController(self)
        self.index_controller = IndexController(self)
        self.menu_controller = MenuController(self)
        self.model_controller = ModelController(self)

        self.change_theme(self.setting.app.ui_style)
        self.search_controller.set_preview_mode(self.setting.app.preview_mode)
        self.search_controller.set_similarity_threshold(self.setting.app.similarity_threshold)
        self.bind_event(first_time=True)
        self.view.after(0, self.__env_init)
        self.view.protocol("WM_DELETE_WINDOW", self.destroy)

    def bind_event(self, first_time=False) -> None:
        search_tab = self.view.search_tab
        index_tab = self.view.index_tab

        self.view.common_setting_btn.config(command=self.open_setting_dialog)
        search_tab.preview_view.bind("<<ItemviewSelect>>", self.search_controller.preview_found_image)
        search_tab.preview_view.bind("<Control-a>", lambda e: search_tab.preview_view.selection_set(tk.ALL))
        search_tab.preview_view.bind("<Control-v>", lambda e: self.search_controller.search_image_by_clipboard())
        preview_widgets = (search_tab.preview_canvas1, search_tab.preview_canvas2, search_tab.preview_view)
        for w in preview_widgets:
            w.bind("<Button-3>", lambda e, w=w: self.menu_controller.create_right_click_menu(e, w))
            w.bind("<Double-Button-1>", lambda e, w=w: self.menu_controller.double_click_open_file(e, w))

        if not first_time:
            return

        search_tab.search_by_browser_btn.config(command=self.search_controller.search_by_browser)
        search_tab.search_by_clipboard_btn.config(command=self.search_controller.search_image_by_clipboard)
        search_tab.search_entry.bind("<Return>", lambda e: self.search_controller.search_image_by_text())
        search_tab.nav_prev.config(command=lambda: self.search_controller._debounce_navigate(-1))
        search_tab.nav_next.config(command=lambda: self.search_controller._debounce_navigate(1))
        search_tab.more_options_button.config(command=self.menu_controller.create_preview_setting_menu)
        search_tab.filter_btn.bind("<Button-1>", lambda e: self.filter_controller.toggle_filter_panel())
        search_tab.filter_panel.confirm_btn.config(command=self.filter_controller.confirm_filter)
        search_tab.filter_panel.cancel_btn.config(command=self.filter_controller.cancel_filter)
        self.view.bind_all("<Button-1>", self.filter_controller.on_root_click)
        self.filter_controller.init_filter_panel()

        index_tab.index_dataset_table.bind("<Double-Button-1>", self.menu_controller.double_click_open_file)
        index_tab.index_dataset_table.bind("<ButtonPress-1>", self.index_controller.drag_start)
        index_tab.index_dataset_table.bind("<B1-Motion>", self.index_controller.drag_motion)
        index_tab.index_dataset_table.bind("<ButtonRelease-1>", self.index_controller.drag_end)
        index_tab.switch_model_combobox.bind("<<ComboboxSelected>>", self.index_controller.switch_model)
        index_tab.switch_model_combobox.bind("<MouseWheel>", lambda _: "break")
        index_tab.switch_model_combobox.bind("<ButtonPress-4>", lambda _: "break")
        index_tab.switch_model_combobox.bind("<ButtonPress-5>", lambda _: "break")
        
        index_tab.add_index_button.config(command=self.index_controller.add_search_dir)
        index_tab.exclude_button.config(command=self.index_controller.open_exclude_dialog)
        index_tab.clean_excluded_button.config(command=self.index_controller.clean_excluded)
        index_tab.update_index_button.config(command=self.index_controller.sync_index)
        index_tab.delete_index_button.config(command=self.index_controller.delete_search_dir)
        index_tab.rebuild_index_button.config(command=self.index_controller.rebuild_index)

        model_tab = self.view.model_tab
        model_tab.model_tree.bind("<<TreeviewSelect>>", self.model_controller.on_model_select)
        model_tab.use_btn.config(command=self.model_controller.switch_model)
        model_tab.uninstall_btn.config(command=self.model_controller.uninstall_model)
        model_tab.download_btn.config(command=self.model_controller.download_model)

        self.view.drop_target_register(DND_FILES)
        self.view.dnd_bind('<<Drop>>', self.__on_drop)

    @decorators.send_task
    def __env_init(self) -> None:
        model_id = self.setting.app.current_model
        self.search_tools = SearchTool(self.setting, model_id)
        self.index_controller.refresh_index_dataset_table()
        self.view.index_tab.update_threads_count_scale.set(self.setting.app.max_work_thread)
        if self.setting.app.auto_update_index:
            self.view.index_tab.auto_update_checkbutton.invoke()
            self.index_controller.sync_index(show_message=False)
        else:
            self.index_controller.update_index_tip()
        self.view.after(self.setting.app.schedule_index_save_interval, self.__schedule_save)
        self.model_controller.load_model_list()
        downloaded_models = self.model_controller.get_downloaded_models()
        self.view.index_tab.switch_model_combobox.config(values=[i.name for i in downloaded_models])
        self.view.index_tab.switch_model_combobox.set(next((i.name for i in downloaded_models if i.id == self.setting.app.current_model), ""))
        self.view.index_tab.update_range_combobox.set("当前模型" if self.setting.app.update_index_range == "current" else "所有模型" )

    def change_theme(self, target_theme: str = "") -> None:
        style = Style()
        valid_theme_names = style.theme_names()
        self.setting.app.ui_style = target_theme if target_theme in valid_theme_names else "superhero"
        default_font = nametofont("TkDefaultFont")
        default_font.configure(family=WinInfo.default_font_family, size=WinInfo.default_font_size)
        self.view.index_tab.index_tip_label.config(font=(WinInfo.default_font_family, -36))
        self.view.search_tab.nav_page_label.config(font=("", -32))
        style.theme_use(self.setting.app.ui_style)
        style.configure('TNotebook.Tab', font=(WinInfo.default_font_family, -36))
        style.configure("Treeview", rowheight=60)
        self.filter_controller._sync_filter_btn_style()

    def open_setting_dialog(self) -> None:
        @decorators.send_task
        def check_for_update() -> None:
            result = update_checker.check()
            if result.error is not None:
                messagebox.showerror("检查更新失败", f"无法检查更新：{result.error}\n\n请检查网络连接后重试。")
                return
            if result.has_update:
                answer = messagebox.askyesno("检查更新", f"发现新版本：v{result.latest_version}\n是否立即更新？")
                if not answer:
                    return
                else:
                    # 实际的更新逻辑
                    pass
            else:
                messagebox.showinfo("检查更新", f"当前版本：v{WinInfo.version}\n你使用的已是最新版本！\n\n仓库地址：{WinInfo.repo_url}")
        
        dialog = SettingDialog(self.view)
        style = Style()
        dialog.theme_combobox.config(values=style.theme_names())
        dialog.theme_combobox.set(self.setting.app.ui_style)
        dialog.theme_combobox.bind("<<ComboboxSelected>>", lambda e: self.change_theme(e.widget.get()))
        if self.setting.app.maximize_window:
            dialog.maximize_checkbutton.invoke()
        dialog.maximize_checkbutton.config(command=lambda: setattr(self.setting.app, 'maximize_window', dialog.maximize_checkbutton.instate(['selected'])))
        dialog.open_settings_file_btn.config(command=lambda: file_ops.open_file(Setting.setting_path))
        dialog.check_update_btn.config(command=check_for_update)

    def __on_drop(self, event) -> None:
        file_paths_str: str = getattr(event, "data")
        file_paths = file_ops.extract_file_paths(file_paths_str)
        tab_id = self.view.switch_tab.index(self.view.switch_tab.select())
        if tab_id == 0:
            self.search_controller.search_by_browser(file_paths)
        elif tab_id == 1:
            for dir_path in file_paths:
                self.index_controller.add_search_dir(dir_path)
        elif tab_id == 2:
            # 这里需要一个本地模型解析的逻辑
            pass
        else:
            pass

    def __schedule_save(self) -> None:
        if self.search_tools:
            self.search_tools.save_index()
        self.view.after(self.setting.app.schedule_index_save_interval, self.__schedule_save)

    def destroy(self) -> None:
        try:
            self.setting.app.auto_update_index = self.view.index_tab.auto_update_checkbutton.instate(['selected'])
            self.setting.app.max_work_thread = int(float(self.view.index_tab.update_threads_count_scale.get()))
            self.setting.app.similarity_threshold = int(float(self.view.search_tab.filter_panel.sim_scale.get()))
            self.setting.app.update_index_range = "current" if self.view.index_tab.update_range_combobox.get() == "当前模型" else "all" 
            self.setting.save()
            self.setting.clean_log()
            if self.search_tools:
                self.search_tools.set_force_end_update(True)
                self.search_tools.save_index()
                self.search_tools.destroy()
            file_ops.rmtree(Setting.temp_image_path)
        except Exception as e:
            messagebox.showerror("错误", str(e))
        finally:
            self.view.destroy()

