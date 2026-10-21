from __future__ import annotations

import tkinter as tk
from tkinter.ttk import Treeview

from ttkbootstrap import Style
from ttkbootstrap.colorutils import color_to_rgb

HOVER_BLEND = 0.5


class HoverHighlight:
    __slots__ = ()

    def _init_hover(self, *extra_targets: tk.Misc) -> None:
        self._hover_item: str = ""
        self._hover_color: str = ""
        self._hover_color_key: tuple[str, str] | None = None
        self._hover_targets: list[tk.Misc] = [self] # type: ignore
        self._bind_hover(self) # type: ignore
        for target in extra_targets:
            self.add_hover_target(target)

    def _identify_hover(self, event: tk.Event) -> str:
        raise NotImplementedError

    def _set_item_hover(self, item: str, hovered: bool) -> None:
        raise NotImplementedError

    def _hover_allowed(self, item: str) -> bool:
        return True

    def _apply_hover_color(self, color: str) -> None:
        ...

    def add_hover_target(self, widget: tk.Misc) -> None:
        self._hover_targets.append(widget)
        self._bind_hover(widget)

    def _bind_hover(self, widget: tk.Misc) -> None:
        widget.bind("<Motion>", self._on_hover_motion, add="+")
        widget.bind("<Leave>", self._on_hover_leave, add="+")
        widget.bind("<MouseWheel>", lambda _: self._clear_hover(), add="+")

    def _on_hover_motion(self, event: tk.Event) -> None:
        item = self._identify_hover(event)
        if item and not self._hover_allowed(item):
            item = ""
        if item == self._hover_item:
            return
        self._clear_hover()
        if not item:
            return
        self._sync_hover_color()
        self._hover_item = item
        self._set_item_hover(item, True)

    def _on_hover_leave(self, event: tk.Event) -> None:
        widget = self.winfo_containing(event.x_root, event.y_root) # type: ignore
        while widget is not None:
            if widget is self:
                return
            widget = getattr(widget, "master", None)
        self._clear_hover()

    def _clear_hover(self) -> None:
        if not self._hover_item:
            return
        item, self._hover_item = self._hover_item, ""
        self._set_item_hover(item, False)

    def _sync_hover_color(self) -> None:
        colors = Style().colors
        key = (colors.selectbg, colors.inputbg) # type: ignore
        if key == self._hover_color_key:
            return
        self._hover_color_key = key
        rgb = [round(b + (s - b) * HOVER_BLEND) for s, b in zip(color_to_rgb(key[0]), color_to_rgb(key[1]))] # type: ignore
        self._hover_color = "#%02x%02x%02x" % tuple(rgb)
        self._apply_hover_color(self._hover_color)


class HoverTreeview(HoverHighlight, Treeview):
    _HOVER_TAG = "_hover"

    def __init__(self, parent, **kwargs) -> None:
        Treeview.__init__(self, parent, **kwargs)
        self._init_hover()

    def _identify_hover(self, event: tk.Event) -> str:
        return self.identify_row(event.y)

    def _set_item_hover(self, item: str, hovered: bool) -> None:
        for tree in self._hover_targets:
            if not tree.exists(item): # type: ignore
                continue
            tags = tuple(t for t in Treeview.item(tree, item, "tags") if t != self._HOVER_TAG) # type: ignore
            Treeview.item(tree, item, tags=(*tags, self._HOVER_TAG) if hovered else tags) # type: ignore

    def _apply_hover_color(self, color: str) -> None:
        for tree in self._hover_targets:
            tree.tag_configure(self._HOVER_TAG, background=color) # type: ignore
