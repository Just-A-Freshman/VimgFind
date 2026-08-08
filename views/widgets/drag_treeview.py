from __future__ import annotations

import time
from typing import Callable

from tkinter.ttk import Treeview
import tkinter as tk



class DragReorderTreeview(Treeview):
    def __init__(self, parent, ghost_column: int = 0, drag_delay: float = 0.3, **kwargs):
        super().__init__(parent, **kwargs)
        self.__ghost_column = ghost_column
        self.__drag_delay = drag_delay
        self.__on_reorder: Callable[[int, int], None] | None = None
        self.__drag_active: bool = False
        self.__drag_source: str | None = None
        self.__drop_target: str | None = None
        self.__insert_before: bool | None = None
        self.__drag_ghost: tk.Toplevel | None = None
        self.__press_time: float = 0.0

        self.bind("<ButtonPress-1>", self.__drag_start)
        self.bind("<B1-Motion>", self.__drag_motion)
        self.bind("<ButtonRelease-1>", self.__drag_end)

    def config(self, *args, on_reorder: Callable | None = None, **kwargs):
        if on_reorder is not None:
            self.__on_reorder = on_reorder
        Treeview.config(self, *args, **kwargs)

    def __drag_start(self, event: tk.Event) -> None:
        item = self.identify_row(event.y)
        self.__drag_source = item if item else None
        self.__drag_active = False
        self.__drop_target = None
        self.__insert_before = None
        self.__drag_ghost = None
        self.__press_time = time.monotonic()

    def __drag_motion(self, event: tk.Event) -> None:
        if not self.__drag_source:
            return

        if not self.__drag_active:
            if time.monotonic() - self.__press_time < self.__drag_delay:
                return
            self.__drag_active = True
            self.__create_drag_ghost(event)

        if self.__drag_ghost:
            self.__drag_ghost.geometry(f"+{event.x_root + 10}+{event.y_root - 5}")

        target = self.identify_row(event.y)

        if not target:
            children = self.get_children()
            if children:
                last_bbox = self.bbox(children[-1])
                if last_bbox and event.y > last_bbox[1] + last_bbox[3]:
                    self.__drop_target = None
                    self.__insert_before = False
                    self.selection_set(children[-1])
                    return
            self.__drop_target = None
            self.__insert_before = None
            self.selection_set(())
            return

        if target == self.__drag_source:
            self.__drop_target = None
            self.__insert_before = None
            self.selection_set(self.__drag_source)
            return

        bbox = self.bbox(target)
        if not bbox:
            return

        children = list(self.get_children())
        _, y, _, height = bbox
        self.__insert_before = (event.y - y) < height // 2
        self.__drop_target = target

        if self.__insert_before:
            self.selection_set(target)
        else:
            next_idx = children.index(target) + 1
            if next_idx < len(children):
                self.selection_set(children[next_idx])
            else:
                self.selection_set(())

    def __drag_end(self, event: tk.Event) -> None:
        if self.__drag_ghost:
            self.__drag_ghost.destroy()
            self.__drag_ghost = None

        if not self.__drag_active or not self.__drag_source:
            self.__drag_clear_state()
            return

        try:
            items = list(self.get_children())
            source_idx = items.index(self.__drag_source)

            if self.__drop_target is None and self.__insert_before is False:
                target_idx = len(items)
            elif self.__drop_target:
                target_idx = items.index(self.__drop_target)
                if not self.__insert_before:
                    target_idx += 1
            else:
                return

            if target_idx == source_idx:
                return

            self.move(self.__drag_source, "", target_idx)
            self.selection_set(self.__drag_source)

            if self.__on_reorder:
                self.__on_reorder(source_idx, target_idx)
        finally:
            self.__drag_clear_state()

    def __create_drag_ghost(self, event: tk.Event) -> None:
        source = self.__drag_source
        if source is None:
            return
        values = self.item(source, "values")
        dir_path = values[self.__ghost_column] if len(values) > 1 else self.item(source, "text")

        ghost = tk.Toplevel(self)
        ghost.overrideredirect(True)
        ghost.attributes("-alpha", 0.75, "-topmost", True)

        label = tk.Label(ghost, text=str(dir_path), anchor=tk.W, padx=12, pady=3)
        label.pack()

        ghost.update_idletasks()
        ghost.geometry(f"+{event.x_root + 10}+{event.y_root - 5}")
        self.__drag_ghost = ghost

    def __drag_clear_state(self) -> None:
        self.__drag_source = None
        self.__drag_active = False
        self.__drop_target = None
        self.__insert_before = None
        self.__drag_ghost = None
