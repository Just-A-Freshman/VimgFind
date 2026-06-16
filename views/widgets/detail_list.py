import tkinter as tk
from tkinter.ttk import Treeview, Scrollbar
import os

from .base import BasicImagePreviewView


class DetailListView(BasicImagePreviewView):
    def __init__(self, parent: tk.Widget, extra_columns: dict[str, int]) -> None:
        super().__init__(parent)
        self._create_treeview(extra_columns)
        self.parent.after(50, self._create_scrollbar)

    def _create_treeview(self, extra_columns: dict[str, int]) -> None:
        columns = {"名称": 160, **extra_columns}
        self.__treeview = Treeview(self.parent, show="headings", columns=list(columns))
        for text, width in columns.items():
            self.__treeview.heading(text, text=text, anchor='center')
            self.__treeview.column(text, anchor='center', width=width, stretch=True)
        self.__treeview.place(relx=0, rely=0, relwidth=1, relheight=1)
        for column in self.__treeview["columns"]:
            self.__treeview.heading(column, command=lambda column=column: self._sort_column(column, False))

    def _create_scrollbar(self) -> None:
        self.__scrollbar = Scrollbar(self.__treeview, orient="vertical", cursor="hand2")
        self.__scrollbar.pack(fill="both", side="right", padx=2, pady=2)
        self.__scrollbar.config(command=self.__treeview.yview)
        self.__treeview.configure(yscrollcommand=self.__scrollbar.set)

    def _get_colomn_idx(self, column) -> int:
        columns: tuple = self.__treeview["columns"]
        return columns.index(column)

    def _sort_column(self, col: str, reverse: bool) -> None:
        data = [(self.__treeview.set(k, col), k) for k in self.__treeview.get_children("")]
        if col == "相似度" or col == "大小":
            data.sort(key=lambda x: f"{x[0]:0>10}", reverse=reverse)
        else:
            data.sort(reverse=reverse)
        for index, (_, k) in enumerate(data):
            self.__treeview.move(k, "", index)
        self.__treeview.heading(col, command=lambda: self._sort_column(col, not reverse))

    def append_result(self, image_path: str, *extra_info: str | int) -> str:
        iid = self._generate_unique_path_item(image_path)
        content = (os.path.basename(image_path), *extra_info)
        self._results[iid] = (image_path, *extra_info)
        return self.__treeview.insert('', tk.END, values=content, iid=iid, text=image_path)

    def clear_results(self) -> None:
        self._results.clear()
        self.__treeview.delete(*self.__treeview.get_children())

    def selection(self) -> tuple[str, ...]:
        return self.__treeview.selection()

    def selection_set(self, *items: str) -> None:
        if not items:
            return
        if items[0] == tk.ALL:
            self.__treeview.selection_set(self.__treeview.get_children(""))
        else:
            self.__treeview.selection_set(items)

    def identify_item(self, event: tk.Event) -> str:
        return self.__treeview.identify_row(event.y)

    def bind(self, sequence: str, func) -> None:
        if sequence == "<<ItemviewSelect>>":
            sequence = "<<TreeviewSelect>>"
        self.__treeview.bind(sequence, func)

    def destroy(self) -> None:
        self.__scrollbar.destroy()
        self.__treeview.destroy()
