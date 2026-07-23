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
    __slots__ = ("parent", "_results", "theme_color")

    def __init__(self, parent: tk.Widget) -> None:
        self.parent = parent
        self._results: OrderedDict[str, tuple] = OrderedDict(dict())
        self.theme_color = self._get_theme_colors()

    def _generate_unique_path_item(self, path: str) -> str:
        norm_path = file_ops.normalize_path(path)
        while norm_path in self._results:
            norm_path += "#"
        return hashlib.md5(norm_path.encode()).hexdigest()[:16]

    def _get_theme_colors(self) -> ThemeColor:
        style = Style()
        style_color = style.colors
        color_attr = [getattr(style_color, field) for field in ThemeColor._fields]
        return ThemeColor(*color_attr)

    def _change_theme(self) -> None:
        self.theme_color = self._get_theme_colors()

    def append(self, image_path: str, *extra_info: Any, **kwargs: Any) -> str:
        return self._generate_unique_path_item(image_path)

    def get_show_results(self) -> list[tuple]:
        return list(self._results.values())

    def clear(self) -> None:
        pass

    def delete(self, *items: str) -> None:
        pass

    def selection(self) -> tuple[str, ...]:
        return ()

    def selection_set(self, *items: str) -> None:
        pass

    def identify_item(self, event: tk.Event) -> str:
        return ""

    def item(self, item) -> tuple:
        return self._results[item]

    def bind(self, sequence: str, func: Callable, add: bool | Literal['', '+'] | None = None) -> None:
        pass

    def destroy(self) -> None:
        pass
