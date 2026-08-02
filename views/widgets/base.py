from __future__ import annotations

from collections import namedtuple
from collections import OrderedDict
from typing import Callable, Literal, Any
import hashlib
import tkinter as tk

from ttkbootstrap import Style

import utils.file_ops as file_ops

ThemeColor = namedtuple("ThemeColor", ["primary", "fg", "selectbg", "inputbg"])


class BasicImagePreviewView:
    __slots__ = ("master", "_results", "theme_color")

    def __init__(self, master: tk.Widget) -> None:
        self.master = master
        self._results: OrderedDict[str, tuple] = OrderedDict(dict())
        self.theme_color = self.get_theme_colors()

    def generate_path_item(self, path: str, unique: bool = True) -> str:
        norm_path = file_ops.normalize_path(path)
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

    def append(self, image_path: str, *extra_info: Any, **kwargs: Any) -> str:
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

    def destroy(self) -> None:
        ...
