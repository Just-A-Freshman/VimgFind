from __future__ import annotations

from collections import namedtuple
from collections import OrderedDict
from typing import Callable, Literal, Any
from pathlib import Path
import hashlib
import tkinter as tk

from ttkbootstrap import Style
from tkinterdnd2 import COPY, DND_FILES

import utils.file_ops as file_ops

ThemeColor = namedtuple("ThemeColor", ["primary", "fg", "selectbg", "inputbg"])


class BasicImagePreviewView:
    __slots__ = ("master", "_results", "theme_color")
    drag_source_active = False

    def __init__(self, master: tk.Widget) -> None:
        self.master = master
        self._results: OrderedDict[str, tuple] = OrderedDict(dict())
        self.theme_color = self.get_theme_colors()
        self.drag_source_register(1, DND_FILES)
        self.dnd_bind('<<DragInitCmd>>', self.on_drag_init)
        self.dnd_bind('<<DragEndCmd>>', self.on_drag_end)

    def generate_path_item(self, path: Path, unique: bool = True) -> str:
        norm_path = file_ops.fast_normalize(path)
        hash_key = hashlib.md5(norm_path.encode()).hexdigest()[:16]
        if not unique:
            return hash_key
        while hash_key in self._results:
            norm_path += "#"
            hash_key = hashlib.md5(norm_path.encode()).hexdigest()[:16]
        return hash_key

    def get_theme_colors(self) -> ThemeColor:
        style = Style()
        style_color = style.colors
        color_attr = [getattr(style_color, field) for field in ThemeColor._fields]
        return ThemeColor(*color_attr)

    def change_theme(self) -> None:
        self.theme_color = self.get_theme_colors()

    def append(self, image_path: Path, *extra_info: Any, **kwargs: Any) -> str:
        return self.generate_path_item(image_path)

    def get_show_results(self) -> list[tuple]:
        return list(self._results.values())

    def clear(self) -> None:
        ...

    def delete(self, *items: str) -> None:
        ...

    def selection(self) -> tuple[str, ...]:
        return ()

    def selection_set(self, *items: str) -> None:
        ...

    def identify_item(self, event: tk.Event) -> str:
        return ""

    def item(self, item: str, option: Literal["values"] = "values") -> tuple:
        return self._results[item]

    def bind(self, sequence: str | None = None, func: Callable | None = None, add: bool | Literal['', '+'] | None = None) -> None:
        ...

    def dnd_bind(self, sequence: str | None = None, func: Callable | None = None, add: bool | Literal['', '+'] | None = None) -> Any:
        ...

    def drag_source_register(self, button: int | None = None, *dndtypes: str) -> None:
        ...

    def on_drag_init(self, event) -> tuple:
        BasicImagePreviewView.drag_source_active = True
        selected = self.selection()
        if not selected:
            return ("", "", "")
        paths = []
        for item in selected:
            if item in self._results:
                path = self._results[item][0]
                if isinstance(path, Path):
                    paths.append(str(path))
        if not paths:
            return ("", "", "")
        return (COPY, DND_FILES, tuple(paths))

    def on_drag_end(self, event) -> None:
        BasicImagePreviewView.drag_source_active = False

    def destroy(self) -> None:
        ...
