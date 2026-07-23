from __future__ import annotations

from tkinter import messagebox
from tkinterdnd2 import DND_FILES

from views import WinGUI
from config.settings import Setting
from core import SearchTool
from .filter_controller import FilterController
from .search_controller import SearchController
from .index_controller import IndexController
from .menu_controller import MenuController
from .model_controller import ModelController
from .setting_controller import SettingController
from utils.i18n import I18n, _
import utils.file_ops as file_ops
import utils.decorators as decorators


class AppController:
    def __init__(self) -> None:
        self.setting = Setting()
        self.view = WinGUI(self.setting.app.maximize_window, self.setting.app.topmost_window)
        self.search_tools: SearchTool | None = None
        
        self.setting_controller = SettingController(self)
        self.search_controller = SearchController(self)
        self.filter_controller = FilterController(self)
        self.menu_controller = MenuController(self)
        self.index_controller = IndexController(self)
        self.model_controller = ModelController(self)
        self.setting_controller.change_theme(self.setting.app.ui_style)
        self.search_controller.set_preview_mode(self.setting.app.preview_mode)
        self.view.after(50, self.env_init)

    @decorators.send_task
    def env_init(self) -> None:
        # bind event
        self.view.common_setting_btn.config(command=lambda: self.setting_controller.show_dialog())
        self.view.bind_all("<Button-1>", self.filter_controller.on_root_click)
        self.view.drop_target_register(DND_FILES)
        self.view.dnd_bind('<<Drop>>', self.__on_drop)
        self.view.protocol("WM_DELETE_WINDOW", self.destroy)

        # env init
        self.search_controller.env_init()
        self.filter_controller.env_init()
        self.search_tools = SearchTool(self.setting)
        self.model_controller.env_init()
        self.index_controller.env_init()
        self.view.after(self.setting.app.schedule_index_save_interval * 1000, self.__schedule_save)
        I18n().load(self.setting.app.locale)

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
            self.model_controller.load_local_model(file_paths[0])
        else:
            pass

    def __schedule_save(self) -> None:
        if self.search_tools:
            self.search_tools.save_index()
        self.view.after(self.setting.app.schedule_index_save_interval * 1000, self.__schedule_save)

    def destroy(self) -> None:
        try:
            if hasattr(self.index_controller, 'idle_tracker'):
                self.index_controller.idle_tracker.stop()
            self.setting.save()
            self.setting.clean_log()
            if self.search_tools:
                self.search_tools.force_stop_update = True
                self.search_tools.save_index()
                self.search_tools.destroy()
            file_ops.rmtree(Setting.temp_image_path)
        except Exception as e:
            messagebox.showerror(_("错误"), str(e))
        finally:
            self.view.destroy()

