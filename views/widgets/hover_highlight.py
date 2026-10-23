from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from tkinter.ttk import Treeview

from ttkbootstrap import Style
from ttkbootstrap.colorutils import color_to_rgb

from config.settings import TkS

HOVER_BLEND = 0.4
HOVER_TIP_DELAY = 800
HOVER_TIP_OFFSET = 50
HOVER_TIP_WRAP = 10000
HOVER_TIP_FADE_STEP = 0.2
HOVER_TIP_FADE_MS = 20
HOVER_CLEAR_DELAY = 80


class Hovertip:
    __slots__ = ("window", "_label", "visible", "_job")

    def __init__(self) -> None:
        self.window: tk.Toplevel | None = None
        self._label: ttk.Label | None = None
        self.visible = False
        self._job: str | None = None

    def prepare(self, master: tk.Misc, text: str) -> tk.Toplevel:
        window = self.window
        if window is None:
            window = tk.Toplevel(master)
            window.overrideredirect(True)
            window.attributes("-topmost", True)
            window.attributes("-alpha", 0.0)
            window.withdraw()
            self._label = ttk.Label(window, wraplength=TkS(HOVER_TIP_WRAP), style="tooltip.TLabel")
            self._label.pack()
            self.window = window
        self._label.config(text=text)    # type: ignore
        return window

    def reveal(self) -> None:
        if self.window is None:
            return
        if not self.visible:
            self.visible = True
            self.window.deiconify()
        self._fade(1.0)

    def hide(self) -> None:
        if self.visible:
            self._fade(0.0)

    @property
    def _alpha(self) -> float:
        return float(self.window.attributes("-alpha")) if self.window is not None else 0.0    # type: ignore

    def _fade(self, target: float) -> None:
        window = self.window
        if window is None:
            return
        if self._job is not None:
            window.after_cancel(self._job)
            self._job = None
        self._step(window, target)

    def _step(self, window: tk.Toplevel, target: float) -> None:
        self._job = None
        if window is not self.window:
            return
        alpha = float(window.attributes("-alpha"))
        if abs(target - alpha) <= HOVER_TIP_FADE_STEP:
            alpha = target
        else:
            alpha += HOVER_TIP_FADE_STEP if target > alpha else -HOVER_TIP_FADE_STEP
        window.attributes("-alpha", alpha)
        if alpha == target:
            if not target:
                window.withdraw()
                self.visible = False
            return
        self._job = window.after(HOVER_TIP_FADE_MS, lambda: self._step(window, target))


class HoverHighlight(tk.Misc):
    __slots__ = ()

    def _init_hover(self, *extra_targets: tk.Misc) -> None:
        self._hover_item: str = ""
        self._hover_color: str = ""
        self._hover_color_key: tuple[str, str] | None = None
        self._hover_targets: list[tk.Misc] = [self]
        self._tip = Hovertip()
        self._tip_job: str | None = None
        self._hover_clear_job: str | None = None
        self._bind_hover(self)
        for target in extra_targets:
            self.add_hover_target(target)

    def _identify_hover(self, event: tk.Event) -> str:
        raise NotImplementedError

    def _set_item_hover(self, item: str, hovered: bool) -> None:
        raise NotImplementedError

    def _hover_allowed(self, item: str) -> bool:
        return True

    def _hover_info(self, item: str) -> str:
        return ""

    def _apply_hover_color(self, color: str) -> None:
        ...

    def add_hover_target(self, widget: tk.Misc) -> None:
        self._hover_targets.append(widget)
        self._bind_hover(widget)

    def _bind_hover(self, widget: tk.Misc) -> None:
        widget.bind("<Motion>", self._on_hover_motion, add="+")
        widget.bind("<Leave>", lambda _: self._clear_hover(), add="+")
        widget.bind("<MouseWheel>", lambda _: self._clear_hover(), add="+")

    def _on_hover_motion(self, event: tk.Event) -> None:
        item = self._identify_hover(event)
        if not item:
            if self._hover_item and self._hover_clear_job is None:
                self._hover_clear_job = self.after(HOVER_CLEAR_DELAY, lambda: setattr(self, "_hover_clear_job", None) or self._clear_hover())
            return
        self._cancel_hover_clear()
        if item == self._hover_item:
            return
        self._clear_hover()
        self._hover_item = item
        if self._hover_allowed(item):
            self._sync_hover_color()
            self._set_item_hover(item, True)
        self._schedule_hover_tip()

    def _clear_hover(self) -> None:
        self._cancel_hover_clear()
        self._cancel_hover_tip()
        item, self._hover_item = self._hover_item, ""
        if item:
            self._set_item_hover(item, False)

    def _cancel_hover_clear(self) -> None:
        if self._hover_clear_job is not None:
            self.after_cancel(self._hover_clear_job)
            self._hover_clear_job = None

    def _schedule_hover_tip(self) -> None:
        self._cancel_hover_tip()
        if self._hover_info(self._hover_item):
            self._tip_job = self.after(HOVER_TIP_DELAY, self._show_hover_tip)

    def _show_hover_tip(self) -> None:
        self._tip_job = None
        if not self.winfo_exists() or not self._hover_item:
            return
        text = self._hover_info(self._hover_item)
        if not text:
            return
        window = self._tip.prepare(self, text)
        window.update_idletasks()
        pointer_x, pointer_y = self.winfo_pointerx(), self.winfo_pointery()
        x, y = pointer_x, pointer_y + HOVER_TIP_OFFSET
        if x + window.winfo_width() > self.winfo_screenwidth():
            x = pointer_x - window.winfo_width() - HOVER_TIP_OFFSET
        if y + window.winfo_height() > self.winfo_screenheight():
            y = pointer_y - window.winfo_height() - HOVER_TIP_OFFSET
        window.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        self._tip.reveal()

    def _cancel_hover_tip(self) -> None:
        if self._tip_job:
            self.after_cancel(self._tip_job)
            self._tip_job = None
        self._tip.hide()

    def _sync_hover_color(self) -> None:
        colors = Style().colors
        key = (colors.selectbg, colors.inputbg)   # type: ignore
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
