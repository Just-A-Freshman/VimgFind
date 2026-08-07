from __future__ import annotations

from typing import Callable, Literal
from pathlib import Path
from tkinter.ttk import Scrollbar
import tkinter as tk
import math
import os

from .base import BasicImagePreviewView
from .image_loader import ImageLoader
from config.settings import TkS
from utils.i18n import _
import utils.file_ops as file_ops


class ThumbnailGridView(tk.Canvas, BasicImagePreviewView):
    MARGIN: int = TkS(10)
    FONT_HEIGHT: int = TkS(32)
    SELECTED_PADDING: int = TkS(3)
    PRELOAD_ROWS: int = 3
    __slots__ = (
        "__thumbnail_size", "__characters_size",
        "__image_loader", "_loading_tasks", "_visible_image_data", 
        "_canvas_items", "_visible_items", "__selected_items", "_scroll_timer",
        "_scrollbar_drag_timer", "__cols", "__is_destroy", "__is_scrollbar_dragging",
    )

    def __init__(self, master: tk.Widget, thumbnail_size: int = 110) -> None:
        tk.Canvas.__init__(self, master)
        BasicImagePreviewView.__init__(self, master)
        self.__env_init()
        self.__thumbnail_size = TkS(thumbnail_size)
        self.__characters_size = int(self.__thumbnail_size / TkS(8))

        self.__image_loader = ImageLoader()
        self.__loading_tasks: set[str] = set()
        self.__visible_image_data: dict[str, dict] = {}

        self.__canvas_items: dict[str, dict[str, int]] = {}
        self.__visible_items: set[str] = set()
        self.__selected_items: set[str] = set()

        self.__scroll_timer: str | None = None
        self.__scrollbar_drag_timer: str | None = None

        self.__cols = 0
        self.__is_destroy = False
        self.__is_scrollbar_dragging = False

        self._check_results()

    def __env_init(self) -> None:
        def create_scrollbar() -> None:
            scrollbar = Scrollbar(self, orient=tk.VERTICAL, cursor="hand2")
            scrollbar.grid(row=0, column=1, sticky=tk.NS, padx=TkS(1), pady=TkS(1))
            self.configure(yscrollcommand=scrollbar.set)
            scrollbar.config(command=self._on_scrollbar_scroll)
            scrollbar.bind("<B1-Motion>", self._on_scrollbar_drag)
            scrollbar.bind("<ButtonRelease-1>", self._on_scrollbar_release)
        self.grid(row=0, column=0, sticky=tk.NSEW)
        self.master.grid_rowconfigure(0, weight=1)
        self.master.grid_columnconfigure(0, weight=1)
        self.update_idletasks()
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.configure(
            takefocus=1,
            background=self.theme_color.inputbg,
            highlightthickness=TkS(0.5),
            highlightbackground=self.theme_color.selectbg,
            highlightcolor=self.theme_color.primary
        )

        # bind event
        self.bind("<Configure>", self._on_canvas_configure)
        self.bind("<MouseWheel>", self._on_mousewheel)
        self.bind("<Button-4>", self._on_mousewheel)
        self.bind("<Button-5>", self._on_mousewheel)
        self.bind("<Button-1>", self._on_canvas_click)
        self.bind("<KeyPress>", self._on_keyboard_click)
        self.bind("<<ThemeChanged>>", lambda e: self.change_theme())
        self.bind("<Enter>", lambda e: self.config(highlightbackground=self.theme_color.primary))
        self.bind("<Leave>", lambda e: self.config(highlightbackground=self.theme_color.selectbg))
        self.bind("<FocusIn>", lambda e: self.config(highlightthickness=TkS(1)))
        self.bind("<FocusOut>", lambda e: self.config(highlightbackground=self.theme_color.selectbg, highlightthickness=TkS(0.5)))
        self.master.after(50, create_scrollbar)

    def change_theme(self) -> None:
        super().change_theme()
        for item_id in self.find_all():
            if self.type(item_id) == "text":
                self.itemconfig(item_id, fill=self.theme_color.fg)
            elif self.type(item_id) == "rectangle":
                self.itemconfig(item_id, fill=self.theme_color.selectbg)
        self.configure(
            background=self.theme_color.inputbg,
            highlightbackground=self.theme_color.primary,
            highlightcolor=self.theme_color.primary,
            highlightthickness=TkS(1)
        )

    def _on_scrollbar_scroll(self, *args) -> None:
        if len(args) == 2:
            self.yview(*args)
        else:
            self.xview(*args)
        self._schedule_load()

    def _on_scrollbar_drag(self, event: tk.Event) -> None:
        def _on_scrollbar_drag_update() -> None:
            if not self.__is_scrollbar_dragging:
                self.__scrollbar_drag_timer = None
                return
            self._load_visible_images()
            if self.__is_scrollbar_dragging:
                self.__scrollbar_drag_timer = self.master.after(50, _on_scrollbar_drag_update)
        self.__is_scrollbar_dragging = True
        if self.__scrollbar_drag_timer:
            self.master.after_cancel(self.__scrollbar_drag_timer)
        self.__scrollbar_drag_timer = self.master.after(50, _on_scrollbar_drag_update)

    def _on_scrollbar_release(self, event: tk.Event) -> None:
        self.__is_scrollbar_dragging = False
        if self.__scrollbar_drag_timer:
            self.master.after_cancel(self.__scrollbar_drag_timer)
            self.__scrollbar_drag_timer = None
        self._schedule_load()

    def _on_mousewheel(self, event: tk.Event) -> None:
        if event.delta:
            delta = int(-1 * (event.delta / 120))
            self.yview_scroll(delta, "units")
        elif event.num == 4:
            self.yview_scroll(-1, "units")
        elif event.num == 5:
            self.yview_scroll(1, "units")
        self._schedule_load()

    def _on_keyboard_click(self, event: tk.Event) -> None:
        if int(event.state) & (0x0001 | 0x0004 | 0x0008):
            return
        monitor_key = ["Left", "KP_Left", "Right", "KP_Right", "Up", "KP_Up", "Down", "KP_Down"]
        if event.keysym not in monitor_key:
            return
        items_list = list(self._results.keys())
        if not items_list or self.__cols == 0:
            return
        target_index = -1
        max_index = len(items_list) - 1
        current_index = max(self._get_item_index(item) for item in self.__selected_items)
        if event.keysym in ("Left", "KP_Left"):
            target_index = max(0, current_index - 1)
        elif event.keysym in ("Right", "KP_Right"):
            target_index = min(max_index, current_index + 1)
        elif event.keysym in ("Up", "KP_Up"):
            target_index = current_index if current_index - self.__cols < 0 else current_index - self.__cols
        elif event.keysym in ("Down", "KP_Down"):
            target_index = current_index if current_index + self.__cols > max_index else current_index + self.__cols
        if target_index == current_index:
            return
        target_item = items_list[target_index]
        self.selection_set(target_item)
        self._scroll_to_item(target_item, event)

    def _scroll_to_item(self, item: str, event: tk.Event) -> None:
        _, y = self._get_item_position(item)
        item_y1 = y
        item_y2 = y + self.__thumbnail_size + self.FONT_HEIGHT
        canvas_y1 = self.canvasy(0)
        canvas_y2 = canvas_y1 + self.winfo_height()
        total_height = self.bbox(tk.ALL)[3] if self.bbox(tk.ALL) else 1
        if item_y2 > canvas_y2:
            self.yview_moveto((item_y2 - self.winfo_height()) / total_height)
        elif item_y1 < canvas_y1:
            self.yview_moveto(item_y1 / total_height)
        self._on_scrollbar_release(event)

    def _on_canvas_configure(self, event) -> None:
        def delayed_resize() -> None:
            self._update_layout()
            self._load_visible_images()
            self.__scroll_timer = None
        if self.__scroll_timer:
            self.master.after_cancel(self.__scroll_timer)
        self.__scroll_timer = self.master.after(100, delayed_resize)

    def _on_canvas_click(self, event: tk.Event) -> None:
        self.focus_set()
        clicked_item = self.identify_item(event)
        if not clicked_item:
            return
        state = int(event.state)
        ctrl_pressed = (state & 0x0004) != 0
        shift_pressed = (state & 0x0001) != 0

        if ctrl_pressed:
            if clicked_item in self.__selected_items:
                self.__selected_items.remove(clicked_item)
                self._set_item_selected(clicked_item, False)
            else:
                self.__selected_items.add(clicked_item)
                self._set_item_selected(clicked_item, True)
        elif shift_pressed:
            if not self.__selected_items:
                self.__selected_items.add(clicked_item)
                self._set_item_selected(clicked_item, True)
            else:
                if clicked_item not in self._results:
                    return
                keys = list(self._results.keys())
                start = next(i for i, k in enumerate(keys) if k == clicked_item or k in self.__selected_items)
                end = keys.index(clicked_item, start)
                collected = keys[start:end + 1]
                if collected:
                    self.selection_set(*collected)
        else:
            self.selection_set(clicked_item)
            self.event_generate("<<ItemviewSelect>>")

    def _schedule_load(self) -> None:
        if self.__scroll_timer:
            self.master.after_cancel(self.__scroll_timer)
        self.__scroll_timer = self.master.after(100, self._load_visible_images)

    def _check_results(self) -> None:
        if self.__is_destroy:
            return
        results = self.__image_loader.get_results()
        for result in results:
            item = result.item
            self.__loading_tasks.discard(item)
            if item not in self._results:
                continue
            self.__visible_image_data[item] = {'photo': result.photo, 'size': result.size, 'error': result.error}
            if item in self.__canvas_items:
                self._create_canvas_item(item)
        self.master.after(100, self._check_results)

    def _cancel_timer(self) -> None:
        if self.__scroll_timer:
            self.master.after_cancel(self.__scroll_timer)
        if self.__scrollbar_drag_timer:
            self.master.after_cancel(self.__scrollbar_drag_timer)

    def _get_item_index(self, item: str) -> int:
        if item not in self.__canvas_items:
            index = next((idx for idx, key in enumerate(self._results) if key == item), -1)
        else:
            index = self.__canvas_items[item]["pos_index"]
        return index

    def _create_placeholder(self, item: str) -> None:
        x, y = self._get_item_position(item)
        filename = os.path.basename(self._results[item][0])
        display_name = file_ops.truncate_filename(filename, self.__characters_size)
        placeholder_id = self.create_text(
            x + self.__thumbnail_size // 2, y + self.__thumbnail_size // 2,
            text=_("图片加载中..."), fill=self.theme_color.fg
        )
        image_info_id = self.create_text(
            x + self.__thumbnail_size // 2,
            y + self.__thumbnail_size + self.MARGIN // 2 + self.FONT_HEIGHT // 2,
            text=display_name, fill=self.theme_color.fg,
        )
        self.__canvas_items[item] = {
            "placeholder_id": placeholder_id,
            "image_info_id": image_info_id,
            "pos_index": len(self._results) - 1
        }

    def _create_canvas_item(self, item: str) -> None:
        if item not in self.__visible_image_data or item not in self.__canvas_items:
            return
        image_data = self.__visible_image_data[item]
        canvas_item = self.__canvas_items[item]
        x, y = self._get_item_position(item)
        filename = file_ops.truncate_filename(self._results[item][0], self.__characters_size)
        if image_data['photo'] is not None:
            tk.Canvas.delete(self, canvas_item["placeholder_id"])
            width, height = image_data["size"]
            tip_info = f"{filename}\n{width} × {height}"
            self.itemconfig(canvas_item["image_info_id"], text=tip_info)
            if "image_id" not in canvas_item:
                image_id = self.create_image(
                    x + self.__thumbnail_size // 2,
                    y + self.__thumbnail_size // 2,
                    image=image_data['photo']
                )
                canvas_item["image_id"] = image_id
            else:
                self.itemconfig(canvas_item["image_id"], image=image_data['photo'])
        else:
            self.itemconfig(canvas_item["placeholder_id"], text=f"{image_data.get('error', _('加载失败'))[:10]}")
            self.itemconfig(canvas_item["image_info_id"], text=filename)

    def _set_item_selected(self, item: str, selected: bool) -> None:
        canvas_item = self.__canvas_items[item]
        if not selected:
            border_id = canvas_item.get("border_id", "")
            if border_id:
                tk.Canvas.delete(self, border_id)
                canvas_item.pop("border_id")
            return
        if canvas_item.get("border_id", ""):
            return
        x, y = self._get_item_position(item)
        pad = ThumbnailGridView.SELECTED_PADDING
        border_id = self.create_rectangle(
            x - pad, y - pad, x + self.__thumbnail_size + pad, y + self.__thumbnail_size + pad,
            fill=self.theme_color.selectbg
        )
        canvas_item["border_id"] = border_id
        self.tag_lower(border_id)

    def _update_layout(self) -> None:
        canvas_width = self.winfo_width()
        canvas_height = self.winfo_height()
        old_cols = self.__cols
        item_width = self.__thumbnail_size + self.MARGIN
        self.__cols = max(1, (canvas_width - self.MARGIN * 2) // item_width)

        if old_cols != self.__cols and old_cols != 0:
            self._reposition_items()

        rows = math.ceil(len(self._results) / self.__cols) if self.__cols > 0 else 0
        item_height = self.__thumbnail_size + self.MARGIN + self.FONT_HEIGHT
        total_height = rows * item_height + self.MARGIN * 2 if rows > 0 else 0
        if total_height > canvas_height:
            self.configure(scrollregion=(0, 0, canvas_width, total_height))
        else:
            self.configure(scrollregion=(0, 0, canvas_width, canvas_height))
            self.yview_moveto(0)

    def _reposition_items(self) -> None:
        for item, canvas_item in self.__canvas_items.items():
            x, y = self._get_item_position(item)
            image_id = canvas_item.get("image_id", "")
            if image_id:
                self.coords(image_id, x + self.__thumbnail_size // 2, y + self.__thumbnail_size // 2)
            border_id = canvas_item.get("border_id", "")
            if border_id:
                self.coords(border_id, x - 4, y - 4, x + self.__thumbnail_size + 4, y + self.__thumbnail_size + 4)
            self.coords(canvas_item["placeholder_id"], x + self.__thumbnail_size // 2, y + self.__thumbnail_size // 2)
            self.coords(canvas_item["image_info_id"], x + self.__thumbnail_size // 2, y + self.__thumbnail_size + self.MARGIN // 2 + self.FONT_HEIGHT // 2)

    def _get_item_position(self, item: str) -> tuple[int, int]:
        if self.__cols == 0:
            return (self.MARGIN, self.MARGIN)
        index = self._get_item_index(item)
        row = index // self.__cols
        col = index % self.__cols
        item_width = self.__thumbnail_size + self.MARGIN
        item_height = self.__thumbnail_size + self.MARGIN + self.FONT_HEIGHT
        x = col * item_width + self.MARGIN + self.MARGIN // 2
        y = row * item_height + self.MARGIN + self.MARGIN // 2
        return (x, y)

    def _load_visible_images(self) -> None:
        if not self._results or self.__cols == 0:
            return
        canvas_y1 = self.canvasy(0)
        canvas_y2 = canvas_y1 + self.winfo_height()
        item_height = self.__thumbnail_size + self.MARGIN + self.FONT_HEIGHT

        start_row = max(0, canvas_y1 // item_height - self.PRELOAD_ROWS)
        end_row = min(math.ceil(len(self._results) / self.__cols), canvas_y2 // item_height + self.PRELOAD_ROWS)
        start_index = int(start_row * self.__cols)
        end_index = int(min(end_row * self.__cols - 1, len(self._results) - 1))
        new_visible_items = set()
        for index, item in enumerate(list(self._results)):
            if index < start_index or index > end_index:
                continue
            new_visible_items.add(item)
            if (item not in self.__visible_image_data and item not in self.__loading_tasks):
                self.__loading_tasks.add(item)
                image_path = self._results[item][0]
                self.__image_loader.add_task(item, image_path, self.__thumbnail_size)
        self.__visible_items = new_visible_items

    def append(self, image_path: Path, *extra_info: str | int) -> str:
        item = self.generate_path_item(image_path)
        self._results[item] = (image_path, *extra_info)
        self._update_layout()
        self._create_placeholder(item)
        self.master.after(100, self._load_visible_images)
        return item
    
    def clear(self) -> None:
        self._cancel_timer()
        self.__loading_tasks.clear()
        self.__visible_image_data.clear()
        self._results.clear()
        self.__canvas_items.clear()
        self.__visible_items.clear()
        self.__selected_items.clear()
        tk.Canvas.delete(self, tk.ALL)
        self._update_layout()

    def delete(self, *items) -> None:
        for key in items:
            canvas_item = self.__canvas_items.pop(key, None)
            if not canvas_item:
                continue
            for field in ("image_id", "placeholder_id", "image_info_id", "border_id"):
                cid = canvas_item.get(field, "")
                if cid:
                    tk.Canvas.delete(self, cid)
            self.__visible_image_data.pop(key, None)
            self.__visible_items.discard(key)
            self.__selected_items.discard(key)
            self.__loading_tasks.discard(key)
            del self._results[key]

        for new_index, key in enumerate(self._results):
            if key in self.__canvas_items:
                self.__canvas_items[key]["pos_index"] = new_index

        self._reposition_items()
        self._update_layout()
        
    def selection(self) -> tuple[str, ...]:
        return tuple([item for item in self._results if item in self.__selected_items])

    def selection_set(self, *items: str) -> None:
        if not items:
            return
        if items[0] == tk.ALL:
            all_need_to_selected_items = set(self._results.keys())
        else:
            all_need_to_selected_items = set(items)
        new_need_to_selected_items = all_need_to_selected_items - self.__selected_items
        need_to_deselected_items = self.__selected_items - all_need_to_selected_items

        for item in new_need_to_selected_items:
            self._set_item_selected(item, True)
        for item in need_to_deselected_items:
            self._set_item_selected(item, False)
        self.__selected_items = all_need_to_selected_items
        self.event_generate("<<ItemviewSelect>>")

    def identify_item(self, event: tk.Event) -> str:
        x = self.canvasx(event.x)
        y = self.canvasy(event.y)

        if not self._results or self.__cols == 0:
            return ""

        item_width = self.__thumbnail_size + self.MARGIN
        item_height = self.__thumbnail_size + self.MARGIN + self.FONT_HEIGHT
        offset = self.MARGIN + self.MARGIN // 2

        col = int((x - offset) // item_width)
        row = int((y - offset) // item_height)

        if col < 0 or col >= self.__cols or row < 0:
            return ""

        index = row * self.__cols + col
        if index >= len(self._results):
            return ""

        cell_x = col * item_width + offset
        cell_y = row * item_height + offset
        if not (cell_x <= x <= cell_x + self.__thumbnail_size and
                cell_y <= y <= cell_y + self.__thumbnail_size):
            return ""

        clicked_item = list(self._results)[index]
        return clicked_item

    def bind(self, sequence: str, func: Callable, add: bool | Literal['', '+'] | None = None) -> None:   # type: ignore
        tk.Canvas.bind(self, sequence, func, add)

    def destroy(self) -> None:
        self.__is_destroy = True
        self._cancel_timer()
        self.__image_loader.stop()
        tk.Canvas.destroy(self)
