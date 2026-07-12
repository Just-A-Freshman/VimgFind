import tkinter as tk
from tkinter.ttk import Treeview

from config.settings import TkS


class DragReorderTreeview(Treeview):
    def __init__(self, parent, on_reorder=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.on_reorder = on_reorder

        self._drag_source: str | None = None
        self._drag_active: bool = False
        self._drop_target: str | None = None
        self._insert_before: bool | None = None
        self._drag_ghost: tk.Toplevel | None = None

        self.bind("<ButtonPress-1>", self._drag_start)
        self.bind("<B1-Motion>", self._drag_motion)
        self.bind("<ButtonRelease-1>", self._drag_end)

    def _drag_start(self, event: tk.Event) -> None:
        item = self.identify_row(event.y)
        self._drag_source = item if item else None
        self._drag_active = False
        self._drop_target = None
        self._insert_before = None
        self._drag_ghost = None

    def _drag_motion(self, event: tk.Event) -> None:
        if not self._drag_source:
            return

        if not self._drag_active:
            self._drag_active = True
            self._create_drag_ghost(event)

        self._move_drag_ghost(event)

        target = self.identify_row(event.y)

        if not target:
            children = self.get_children()
            if children:
                last_bbox = self.bbox(children[-1])
                if last_bbox and event.y > last_bbox[1] + last_bbox[3]:
                    self._drop_target = None
                    self._insert_before = False
                    self.selection_set(children[-1])
                    return
            self._drop_target = None
            self._insert_before = None
            self.selection_set(())
            return

        if target == self._drag_source:
            self._drop_target = None
            self._insert_before = None
            self.selection_set(self._drag_source)
            return

        bbox = self.bbox(target)
        if not bbox:
            return

        children = list(self.get_children())
        _, y, _, height = bbox
        self._insert_before = (event.y - y) < height // 2
        self._drop_target = target

        if self._insert_before:
            self.selection_set(target)
        else:
            next_idx = children.index(target) + 1
            if next_idx < len(children):
                self.selection_set(children[next_idx])
            else:
                self.selection_set(())

    def _drag_end(self, event: tk.Event) -> None:
        if self._drag_ghost:
            self._drag_ghost.destroy()
            self._drag_ghost = None

        if not self._drag_active or not self._drag_source:
            self._drag_clear_state()
            return

        try:
            items = list(self.get_children())
            source_idx = items.index(self._drag_source)

            if self._drop_target is None and self._insert_before is False:
                target_idx = len(items)
            elif self._drop_target:
                target_idx = items.index(self._drop_target)
                if not self._insert_before:
                    target_idx += 1
            else:
                return

            if target_idx == source_idx:
                return

            self.move(self._drag_source, "", target_idx)
            for i, item in enumerate(self.get_children(), 1):
                _, dir_path = self.item(item, "values")
                self.item(item, values=(i, dir_path))

            self.selection_set(self._drag_source)

            if self.on_reorder:
                self.on_reorder(source_idx, target_idx)
        finally:
            self._drag_clear_state()

    def _create_drag_ghost(self, event: tk.Event) -> None:
        source = self._drag_source
        if source is None:
            return
        values = self.item(source, "values")
        dir_path = values[1] if len(values) > 1 else ""

        ghost = tk.Toplevel(self)
        ghost.overrideredirect(True)
        ghost.attributes("-alpha", 0.75, "-topmost", True)

        label = tk.Label(ghost, text=str(dir_path), anchor=tk.W,
                         padx=TkS(12), pady=TkS(3))
        label.pack()

        ghost.update_idletasks()
        ghost.geometry(f"+{event.x_root + TkS(10)}+{event.y_root - TkS(5)}")
        self._drag_ghost = ghost

    def _move_drag_ghost(self, event: tk.Event) -> None:
        if self._drag_ghost:
            self._drag_ghost.geometry(
                f"+{event.x_root + TkS(10)}+{event.y_root - TkS(5)}"
            )

    def _drag_clear_state(self) -> None:
        self._drag_source = None
        self._drag_active = False
        self._drop_target = None
        self._insert_before = None
        self._drag_ghost = None
