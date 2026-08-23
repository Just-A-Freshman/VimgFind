from __future__ import annotations

from typing import Callable, Literal
from pathlib import Path
from tkinter.ttk import Treeview, Scrollbar
import tkinter as tk


from .base import BasicImagePreviewView
from config.settings import TkS
from utils.i18n import _
from tkinterdnd2 import DND_FILES


class DetailListView(Treeview, BasicImagePreviewView):   # type:ignore
    def __init__(self, master: tk.Widget, extra_columns: dict[str, int]) -> None:
        columns = {_("名称"): TkS(80), **extra_columns}
        Treeview.__init__(self, master, show="headings", columns=list(columns), padding=TkS(1))
        BasicImagePreviewView.__init__(self, master)
        self.__env_init(columns)
        
    def __env_init(self, columns: dict[str, int]) -> None:
        def create_scrollbar() -> None:
            scrollbar = Scrollbar(self, orient=tk.VERTICAL, cursor="hand2")
            scrollbar.pack(fill=tk.BOTH, side=tk.RIGHT, padx=TkS(1), pady=TkS(1))
            scrollbar.config(command=self.yview)
            self.configure(yscrollcommand=scrollbar.set)
        for text, width in columns.items():
            self.heading(text, text=text, anchor=tk.CENTER)
            self.column(text, anchor=tk.CENTER, width=width, stretch=True)
        self.grid(row=0, column=0, sticky=tk.NSEW)
        self.master.grid_rowconfigure(0, weight=1)
        self.master.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        for column in self["columns"]:
            self.heading(column, command=lambda column=column: self.__sort_column(column, False))
        self.master.after(50, create_scrollbar)
        self.drag_source_register(1, DND_FILES)
        self.dnd_bind('<<DragInitCmd>>', self.on_drag_init)
        self.dnd_bind('<<DragEndCmd>>', self.on_drag_end)

    def __sort_column(self, col: str, reverse: bool) -> None:
        data = [(self.set(k, col), k) for k in self.get_children("")]
        if col == _("相似度") or col == _("大小"):
            data.sort(key=lambda x: float(x[0].rstrip("MB%")), reverse=reverse)
        else:
            data.sort(reverse=reverse)
        for index, (tmp, k) in enumerate(data):
            self.move(k, "", index)
        self.heading(col, command=lambda: self.__sort_column(col, not reverse))

    def append(self, image_path: Path, *extra_info: str | int) -> str:
        iid = self.generate_path_item(image_path)
        content = (image_path.name, *extra_info)
        self._results[iid] = (image_path, *extra_info)
        return self.insert('', tk.END, values=content, iid=iid)    

    def clear(self) -> None:
        self._results.clear()
        Treeview.delete(self, *self.get_children())

    def delete(self, *items) -> None:
        Treeview.delete(self, *items)
        for item in items:
            self._results.pop(str(item))

    def selection(self) -> tuple[str, ...]:
        return Treeview.selection(self)

    def selection_set(self, *args, **kwargs) -> None:
        Treeview.selection_set(self, *self.get_children("")) if len(args) == 1 and args[0] == tk.ALL else Treeview.selection_set(self, *args, **kwargs)

    def identify_item(self, event: tk.Event) -> str:
        return Treeview.identify_row(self, event.y)

    def item(self, item: str, option: Literal["values"] = "values") -> tuple:      # type: ignore
        return BasicImagePreviewView.item(self, item, option)
    
    def bind(self, sequence: str | None, func: Callable, add: bool | Literal['', '+'] | None = None) -> None:   # type: ignore
        sequence = "<<TreeviewSelect>>" if sequence == "<<ItemviewSelect>>" else sequence
        Treeview.bind(self, sequence, func, add)

    def destroy(self) -> None:
        Treeview.destroy(self)
