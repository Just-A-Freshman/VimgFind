from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
import tkinter as tk

from utils.i18n import _

if TYPE_CHECKING:
    from .app_controller import AppController


@dataclass
class _FilterSnapshot:
    threshold: float = 0.0
    ext: str = ""
    size_min: str = ""
    size_min_unit: str = ""
    size_max: str = ""
    size_max_unit: str = ""
    folder_selection: tuple = ()
    folder_all: bool = True


class FilterController:
    def __init__(self, app_controller: AppController) -> None:
        self.app = app_controller
        self._folder_all_var = tk.BooleanVar(value=True)
        self._folder_paths: list[str] = []
        self._saved_state: _FilterSnapshot | None = None

    def env_init(self) -> None:
        fp = self.app.view.search_tab.filter_panel
        fp.sim_scale.set(self.app.search_controller.similarity_threshold)
        fp.sim_value.config(text=f"{int(self.app.search_controller.similarity_threshold)}%")
        fp.sim_scale.config(
            command=lambda value: (
                fp.sim_value.config(text=f"{int(float(value))}%"),
                self.app.search_controller.set_similarity_threshold(float(value))
            )
        )
        self.refresh_folder_filter()
        fp.folder_select_all.config(variable=self._folder_all_var, command=self.__on_folder_select_all)
        fp.folder_listbox.bind("<<ListboxSelect>>", self.__on_folder_listbox_select)
        self.__on_folder_select_all()

    def refresh_folder_filter(self) -> None:
        dirs = self.app.setting.model.index.search_dir
        self._folder_paths = list(dirs)
        lb = self.app.view.search_tab.filter_panel.folder_listbox
        lb.delete(0, tk.END)
        for d in self._folder_paths:
            lb.insert(tk.END, d)

    def get_search_filters(self) -> tuple:
        def parse_size(text: str, unit: str) -> float | None:
            t = text.strip()
            try:
                value = float(t) if t else None
            except ValueError:
                return None
            if value is None:
                return None
            return value / 1024 if unit == "KB" else value
        
        fp = self.app.view.search_tab.filter_panel
        ext = fp.ext_combo.get()
        size_min = parse_size(fp.size_min.get(), fp.size_min_unit.get())
        size_max = parse_size(fp.size_max.get(), fp.size_max_unit.get())
        if self._folder_all_var.get():
            folder_filters = None
        else:
            selected = fp.folder_listbox.curselection()
            folder_filters = [self._folder_paths[i] for i in selected] or None
        dedup = fp.dedup_check.instate(['selected'])
        return ext, size_min, size_max, folder_filters, dedup

    def toggle_filter_panel(self) -> None:
        fp = self.app.view.search_tab.filter_panel
        if fp.winfo_viewable():
            fp.place_forget()
        else:
            self.__save_filter_state()
            fp.update_idletasks()
            fp.place(relx=0.005, rely=0.094, relwidth=0.4, height=fp.winfo_reqheight())
            fp.lift()

    def confirm_filter(self) -> None:
        self.app.view.search_tab.filter_panel.place_forget()
        self.app.search_controller.resend_last_search()

    def cancel_filter(self) -> None:
        s = self._saved_state
        if s is None:
            return
        fp = self.app.view.search_tab.filter_panel
        self.app.search_controller.set_similarity_threshold(s.threshold)
        fp.sim_scale.set(s.threshold)
        fp.sim_value.config(text=f"{int(s.threshold)}%")
        fp.ext_combo.set(s.ext)
        fp.size_min.delete(0, tk.END)
        fp.size_min.insert(0, s.size_min)
        fp.size_min_unit.set(s.size_min_unit)
        fp.size_max.delete(0, tk.END)
        fp.size_max.insert(0, s.size_max)
        fp.size_max_unit.set(s.size_max_unit)
        fp.folder_listbox.selection_clear(0, tk.END)
        for idx in s.folder_selection:
            fp.folder_listbox.selection_set(idx)
        self._folder_all_var.set(s.folder_all)
        self.app.view.search_tab.filter_panel.place_forget()

    def on_root_click(self, event) -> None:
        fp = self.app.view.search_tab.filter_panel
        if not fp.winfo_viewable():
            return
        w = event.widget
        if w == self.app.view.search_tab.filter_btn:
            return
        while w:
            if w == fp or isinstance(w, str):
                return
            w = w.master
        self.cancel_filter()

    def __on_folder_select_all(self) -> None:
        lb = self.app.view.search_tab.filter_panel.folder_listbox
        if self._folder_all_var.get():
            lb.selection_set(0, tk.END)
        else:
            lb.selection_clear(0, tk.END)

    def __on_folder_listbox_select(self, *_) -> None:
        lb = self.app.view.search_tab.filter_panel.folder_listbox
        all_selected = len(lb.curselection()) == lb.size()
        self._folder_all_var.set(all_selected)

    def __save_filter_state(self) -> None:
        fp = self.app.view.search_tab.filter_panel
        self._saved_state = _FilterSnapshot(
            threshold=self.app.search_controller.similarity_threshold,
            ext=fp.ext_combo.get(),
            size_min=fp.size_min.get(),
            size_min_unit=fp.size_min_unit.get(),
            size_max=fp.size_max.get(),
            size_max_unit=fp.size_max_unit.get(),
            folder_selection=fp.folder_listbox.curselection(),
            folder_all=self._folder_all_var.get(),
        )
