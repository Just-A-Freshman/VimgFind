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
    __slots__ = ("master", "_results", "theme_color", "_press_info")
    drag_source_active = False

    def __init__(self, master: tk.Widget) -> None:
        self.master = master
        self._results: OrderedDict[str, tuple] = OrderedDict(dict())
        self._press_info = None
        self.theme_color = self.get_theme_colors()
        self.drag_source_register(1, DND_FILES)
        self.dnd_bind('<<DragInitCmd>>', self.on_drag_init)
        self.dnd_bind('<<DragEndCmd>>', self.on_drag_end)

    def _on_press(self, event: tk.Event) -> str | None:
        self.focus_set()
        item = self.identify_item(event)
        if not item:
            self._press_info = None
            return
        ctrl = (int(event.state) & 0x0004) != 0
        shift = (int(event.state) & 0x0001) != 0
        was_selected = item in self.selection()
        self._press_info = {
            'item': item,
            'x': event.x_root,
            'y': event.y_root,
            'was_selected': was_selected,
            'drag_started': False,
            'ctrl': ctrl,
            'shift': shift,
        }
        if not was_selected or ctrl or shift:
            self._handle_click(item, ctrl, shift)
            self._press_info['selection_applied'] = True
        else:
            self._press_info['selection_applied'] = False

    def _on_release(self, event: tk.Event) -> None:
        info = self._press_info
        if not info:
            return
        self._press_info = None
        if info['drag_started']:
            return
        if not info.get('selection_applied', False):
            self._handle_click(info['item'], info['ctrl'], info['shift'])

    def _handle_click(self, item: str, ctrl: bool, shift: bool) -> None:
        ...

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

    def focus_set(self) -> None:
        ...

    def on_drag_init(self, event) -> tuple:
        BasicImagePreviewView.drag_source_active = True
        if self._press_info:
            self._press_info['drag_started'] = True
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
