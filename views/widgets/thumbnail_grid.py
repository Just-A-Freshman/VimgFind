import tkinter as tk
from tkinter.ttk import Scrollbar
import math
import os

import utils.file_ops as file_ops
from .base import BasicImagePreviewView
from .image_loader import ImageLoader
from config.settings import TkS


class ThumbnailGridView(BasicImagePreviewView):
    MARGIN: int = TkS(10)
    FONT_HEIGHT: int = TkS(32)
    PRELOAD_ROWS: int = 3

    def __init__(self, parent: tk.Widget, thumbnail_size: int = 110) -> None:
        super().__init__(parent)
        self._create_canvas()
        self.parent.after(50, self._create_scrollbar)
        self._thumbnail_size = TkS(thumbnail_size)
        self._characters_size = int(self._thumbnail_size / TkS(8))

        self._image_loader = ImageLoader()
        self._loading_tasks: set[str] = set()
        self._visible_image_data: dict[str, dict] = {}

        self._tooltip = None
        self._canvas_items: dict[str, dict[str, int]] = {}
        self._visible_items: set[str] = set()
        self._selected_items: set[str] = set()

        self._scroll_timer: str | None = None
        self._scrollbar_drag_timer: str | None = None

        self._cols = 0
        self._is_destroy = False
        self._is_scrollbar_dragging = False

        self._bind_event()
        self._check_results()

    def _create_canvas(self) -> None:
        self._canvas = tk.Canvas(self.parent)
        self._canvas.grid(row=0, column=0, sticky=tk.NSEW)
        self.parent.grid_rowconfigure(0, weight=1)
        self.parent.grid_columnconfigure(0, weight=1)
        self._canvas.grid_columnconfigure(0, weight=1)
        self._canvas.grid_rowconfigure(0, weight=1)
        self._canvas.configure(
            takefocus=1,
            background=self.theme_color.inputbg,
            highlightthickness=TkS(1),
            highlightbackground=self.theme_color.primary,
            highlightcolor=self.theme_color.primary
        )
        self._canvas.update()

    def _create_scrollbar(self) -> None:
        self._scrollbar = Scrollbar(self._canvas, orient=tk.VERTICAL, cursor="hand2")
        self._scrollbar.grid(row=0, column=1, sticky=tk.NS, padx=TkS(1), pady=TkS(1))
        self._canvas.configure(yscrollcommand=self._scrollbar.set)
        self._scrollbar.config(command=self._on_scrollbar_scroll)
        self._scrollbar.bind("<B1-Motion>", self._on_scrollbar_drag)
        self._scrollbar.bind("<ButtonRelease-1>", self._on_scrollbar_release)

    def _bind_event(self) -> None:
        self._canvas.bind("<Configure>", self._on_canvas_configure)
        self._canvas.bind("<MouseWheel>", self._on_mousewheel)
        self._canvas.bind("<Button-4>", self._on_mousewheel)
        self._canvas.bind("<Button-5>", self._on_mousewheel)
        self._canvas.bind("<Button-1>", self._on_canvas_click)
        self._canvas.bind("<KeyPress>", self._on_keyboard_click)
        self._canvas.bind("<<ThemeChanged>>", lambda e: self._change_theme())
        self._canvas.bind("<Enter>", lambda e: self._canvas.config(highlightbackground=self.theme_color.primary))
        self._canvas.bind("<Leave>", lambda e: self._canvas.config(highlightbackground=self.theme_color.selectbg))
        self._canvas.bind("<FocusIn>", lambda e: self._canvas.config(highlightthickness=TkS(1)))
        self._canvas.bind("<FocusOut>", lambda e: self._canvas.config(highlightthickness=TkS(1)))

    def _change_theme(self) -> None:
        super()._change_theme()
        for item_id in self._canvas.find_all():
            if self._canvas.type(item_id) == "text":
                self._canvas.itemconfig(item_id, fill=self.theme_color.fg)
            elif self._canvas.type(item_id) == "rectangle":
                self._canvas.itemconfig(item_id, fill=self.theme_color.selectbg)
        self._canvas.configure(
            background=self.theme_color.inputbg,
            highlightbackground=self.theme_color.primary,
            highlightcolor=self.theme_color.primary,
            highlightthickness=TkS(1)
        )

    def _on_scrollbar_scroll(self, *args) -> None:
        if len(args) == 2:
            self._canvas.yview(*args)
        else:
            self._canvas.xview(*args)
        self._schedule_load()

    def _on_scrollbar_drag(self, event: tk.Event) -> None:
        def _on_scrollbar_drag_update() -> None:
            if not self._is_scrollbar_dragging:
                self._scrollbar_drag_timer = None
                return
            self._load_visible_images()
            if self._is_scrollbar_dragging:
                self._scrollbar_drag_timer = self.parent.after(50, _on_scrollbar_drag_update)
        self._is_scrollbar_dragging = True
        if self._scrollbar_drag_timer:
            self.parent.after_cancel(self._scrollbar_drag_timer)
        self._scrollbar_drag_timer = self.parent.after(50, _on_scrollbar_drag_update)

    def _on_scrollbar_release(self, event: tk.Event) -> None:
        self._is_scrollbar_dragging = False
        if self._scrollbar_drag_timer:
            self.parent.after_cancel(self._scrollbar_drag_timer)
            self._scrollbar_drag_timer = None
        self._schedule_load()

    def _on_mousewheel(self, event: tk.Event) -> None:
        if event.delta:
            delta = int(-1 * (event.delta / 120))
            self._canvas.yview_scroll(delta, "units")
        elif event.num == 4:
            self._canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self._canvas.yview_scroll(1, "units")
        self._schedule_load()

    def _on_keyboard_click(self, event: tk.Event) -> None:
        monitor_key = ["Left", "KP_Left", "Right", "KP_Right", "Up", "KP_Up", "Down", "KP_Down"]
        if event.keysym not in monitor_key:
            return
        items_list = list(self._results.keys())
        if not items_list or self._cols == 0:
            return
        target_index = -1
        max_index = len(items_list) - 1
        current_index = max(self._get_item_index(item) for item in self._selected_items)
        if event.keysym in ("Left", "KP_Left"):
            target_index = max(0, current_index - 1)
        elif event.keysym in ("Right", "KP_Right"):
            target_index = min(max_index, current_index + 1)
        elif event.keysym in ("Up", "KP_Up"):
            target_index = current_index if current_index - self._cols < 0 else current_index - self._cols
        elif event.keysym in ("Down", "KP_Down"):
            target_index = current_index if current_index + self._cols > max_index else current_index + self._cols
        if target_index == current_index:
            return
        target_item = items_list[target_index]
        self.selection_set(target_item)
        self._scroll_to_item(target_item, event)

    def _scroll_to_item(self, item: str, event: tk.Event) -> None:
        _, y = self._get_item_position(item)
        item_y1 = y
        item_y2 = y + self._thumbnail_size + self.FONT_HEIGHT
        canvas_y1 = self._canvas.canvasy(0)
        canvas_y2 = canvas_y1 + self._canvas.winfo_height()
        total_height = self._canvas.bbox(tk.ALL)[3] if self._canvas.bbox(tk.ALL) else 1
        if item_y2 > canvas_y2:
            self._canvas.yview_moveto((item_y2 - self._canvas.winfo_height()) / total_height)
        elif item_y1 < canvas_y1:
            self._canvas.yview_moveto(item_y1 / total_height)
        self._on_scrollbar_release(event)

    def _on_canvas_configure(self, event) -> None:
        def delayed_resize() -> None:
            self._update_layout()
            self._load_visible_images()
            self._scroll_timer = None
        if self._scroll_timer:
            self.parent.after_cancel(self._scroll_timer)
        self._scroll_timer = self.parent.after(100, delayed_resize)

    def _on_canvas_click(self, event: tk.Event) -> None:
        self._canvas.focus_set()
        clicked_item = self.identify_item(event)
        if not clicked_item:
            return
        state = int(event.state)
        ctrl_pressed = (state & 0x0004) != 0
        shift_pressed = (state & 0x0001) != 0

        if ctrl_pressed:
            if clicked_item in self._selected_items:
                self._selected_items.remove(clicked_item)
                self._set_item_selected(clicked_item, False)
            else:
                self._selected_items.add(clicked_item)
                self._set_item_selected(clicked_item, True)
        elif shift_pressed:
            if not self._selected_items:
                self._selected_items.add(clicked_item)
                self._set_item_selected(clicked_item, True)
            else:
                clicked_index = self._get_item_index(clicked_item)
                if clicked_index == -1:
                    return
                closest_selected_item = closest_selected_index = None
                closest_distance = float('inf')
                for selected_item in self._selected_items:
                    selected_index = self._get_item_index(selected_item)
                    if selected_index == -1:
                        continue
                    curr_distance = abs(selected_index - clicked_index)
                    if curr_distance < closest_distance:
                        closest_distance = curr_distance
                        closest_selected_item = selected_item
                        closest_selected_index = selected_index
                if closest_selected_item is None or closest_selected_index is None:
                    self.selection_set(clicked_item)
                    return
                start_index = min(closest_selected_index, clicked_index)
                end_index = max(closest_selected_index, clicked_index)
                range_selected_items = set()
                for index, item in enumerate(self._results):
                    if start_index <= index <= end_index:
                        range_selected_items.add(item)
                self.selection_set(*range_selected_items)
        else:
            self.selection_set(clicked_item)
            self._canvas.event_generate("<<ItemviewSelect>>")

    def _schedule_load(self) -> None:
        if self._scroll_timer:
            self.parent.after_cancel(self._scroll_timer)
        self._scroll_timer = self.parent.after(100, self._load_visible_images)

    def _check_results(self) -> None:
        if self._is_destroy:
            return
        results = self._image_loader.get_results()
        for result in results:
            item = result.item
            self._loading_tasks.discard(item)
            if item not in self._results:
                continue
            self._visible_image_data[item] = {'photo': result.photo, 'size': result.size, 'error': result.error}
            if item in self._canvas_items:
                self._create_canvas_item(item)
        self.parent.after(100, self._check_results)

    def _cancel_timer(self) -> None:
        if self._scroll_timer:
            self.parent.after_cancel(self._scroll_timer)
        if self._scrollbar_drag_timer:
            self.parent.after_cancel(self._scrollbar_drag_timer)

    def _get_item_index(self, item: str) -> int:
        if item not in self._canvas_items:
            index = next((idx for idx, key in enumerate(self._results) if key == item), -1)
        else:
            index = self._canvas_items[item]["pos_index"]
        return index

    def _create_placeholder(self, item: str) -> None:
        x, y = self._get_item_position(item)
        filename = os.path.basename(self._results[item][0])
        display_name = file_ops.truncate_filename(filename, self._characters_size)
        placeholder_id = self._canvas.create_text(
            x + self._thumbnail_size // 2, y + self._thumbnail_size // 2,
            text="图片加载中...", fill=self.theme_color.fg
        )
        image_info_id = self._canvas.create_text(
            x + self._thumbnail_size // 2,
            y + self._thumbnail_size + self.MARGIN // 2 + self.FONT_HEIGHT // 2,
            text=display_name, fill=self.theme_color.fg,
        )
        self._canvas_items[item] = {
            "placeholder_id": placeholder_id,
            "image_info_id": image_info_id,
            "pos_index": len(self._results) - 1
        }

    def _create_canvas_item(self, item: str) -> None:
        if item not in self._visible_image_data or item not in self._canvas_items:
            return
        image_data = self._visible_image_data[item]
        canvas_item = self._canvas_items[item]
        x, y = self._get_item_position(item)
        filename = file_ops.truncate_filename(self._results[item][0], self._characters_size)
        if image_data['photo'] is not None:
            self._canvas.delete(canvas_item["placeholder_id"])
            width, height = image_data["size"]
            tip_info = f"{filename}\n{width} × {height}"
            self._canvas.itemconfig(canvas_item["image_info_id"], text=tip_info)
            if "image_id" not in canvas_item:
                image_id = self._canvas.create_image(
                    x + self._thumbnail_size // 2,
                    y + self._thumbnail_size // 2,
                    image=image_data['photo']
                )
                canvas_item["image_id"] = image_id
            else:
                self._canvas.itemconfig(canvas_item["image_id"], image=image_data['photo'])
        else:
            self._canvas.itemconfig(canvas_item["placeholder_id"], text=f"{image_data.get('error', '加载失败')[:10]}")
            self._canvas.itemconfig(canvas_item["image_info_id"], text=filename)

    def _set_item_selected(self, item: str, selected: bool) -> None:
        canvas_item = self._canvas_items[item]
        if not selected:
            border_id = canvas_item.get("border_id", "")
            if border_id:
                self._canvas.delete(border_id)
                canvas_item.pop("border_id")
            return
        if canvas_item.get("border_id", ""):
            return
        x, y = self._get_item_position(item)
        border_id = self._canvas.create_rectangle(
            x - 4, y - 4, x + self._thumbnail_size + 4, y + self._thumbnail_size + 4,
            fill=self.theme_color.selectbg
        )
        canvas_item["border_id"] = border_id
        self._canvas.tag_lower(border_id)

    def _update_layout(self) -> None:
        canvas_width = self._canvas.winfo_width()
        canvas_height = self._canvas.winfo_height()
        old_cols = self._cols
        item_width = self._thumbnail_size + self.MARGIN
        self._cols = max(1, (canvas_width - self.MARGIN * 2) // item_width)

        if old_cols != self._cols and old_cols != 0:
            for item, canvas_item in self._canvas_items.items():
                x, y = self._get_item_position(item)
                image_id = canvas_item.get("image_id", "")
                if image_id:
                    self._canvas.coords(image_id, x + self._thumbnail_size // 2, y + self._thumbnail_size // 2)
                border_id = canvas_item.get("border_id", "")
                if border_id:
                    self._canvas.coords(border_id, x - 4, y - 4, x + self._thumbnail_size + 4, y + self._thumbnail_size + 4)
                self._canvas.coords(canvas_item["placeholder_id"], x + self._thumbnail_size // 2, y + self._thumbnail_size // 2)
                self._canvas.coords(canvas_item["image_info_id"], x + self._thumbnail_size // 2, y + self._thumbnail_size + self.MARGIN // 2 + self.FONT_HEIGHT // 2)

        rows = math.ceil(len(self._results) / self._cols) if self._cols > 0 else 0
        item_height = self._thumbnail_size + self.MARGIN + self.FONT_HEIGHT
        total_height = rows * item_height + self.MARGIN * 2 if rows > 0 else 0
        if total_height > canvas_height:
            self._canvas.configure(scrollregion=(0, 0, canvas_width, total_height))
        else:
            self._canvas.configure(scrollregion=(0, 0, canvas_width, canvas_height))
            self._canvas.yview_moveto(0)

    def _get_item_position(self, item: str) -> tuple[int, int]:
        if self._cols == 0:
            return (self.MARGIN, self.MARGIN)
        index = self._get_item_index(item)
        row = index // self._cols
        col = index % self._cols
        item_width = self._thumbnail_size + self.MARGIN
        item_height = self._thumbnail_size + self.MARGIN + self.FONT_HEIGHT
        x = col * item_width + self.MARGIN + self.MARGIN // 2
        y = row * item_height + self.MARGIN + self.MARGIN // 2
        return (x, y)

    def _load_visible_images(self) -> None:
        if not self._results or self._cols == 0:
            return
        canvas_y1 = self._canvas.canvasy(0)
        canvas_y2 = canvas_y1 + self._canvas.winfo_height()
        item_height = self._thumbnail_size + self.MARGIN + 30

        start_row = max(0, canvas_y1 // item_height - self.PRELOAD_ROWS)
        end_row = min(math.ceil(len(self._results) / self._cols), canvas_y2 // item_height + self.PRELOAD_ROWS)
        start_index = int(start_row * self._cols)
        end_index = int(min(end_row * self._cols - 1, len(self._results) - 1))
        new_visible_items = set()
        for index, item in enumerate(self._results):
            if index < start_index or index > end_index:
                continue
            new_visible_items.add(item)
            if (item not in self._visible_image_data and item not in self._loading_tasks):
                self._loading_tasks.add(item)
                image_path = self._results[item][0]
                self._image_loader.add_task(item, image_path, self._thumbnail_size)
        self._visible_items = new_visible_items

    def append_result(self, image_path: str, *extra_info: str | int) -> str:
        item = self._generate_unique_path_item(image_path)
        self._results[item] = (image_path, *extra_info)
        self._update_layout()
        self._create_placeholder(item)
        self.parent.after(100, self._load_visible_images)
        return item

    def clear_results(self) -> None:
        self._cancel_timer()
        self._loading_tasks.clear()
        self._visible_image_data.clear()
        self._results.clear()
        self._canvas_items.clear()
        self._visible_items.clear()
        self._selected_items.clear()
        self._canvas.delete(tk.ALL)
        self._update_layout()

    def selection(self) -> tuple[str, ...]:
        return tuple(self._selected_items)

    def selection_set(self, *items: str) -> None:
        if not items:
            return
        if items[0] == tk.ALL:
            all_need_to_selected_items = set(self._results.keys())
        else:
            all_need_to_selected_items = set(items)
        new_need_to_selected_items = all_need_to_selected_items - self._selected_items
        need_to_deselected_items = self._selected_items - all_need_to_selected_items

        for item in new_need_to_selected_items:
            self._set_item_selected(item, True)
        for item in need_to_deselected_items:
            self._set_item_selected(item, False)
        self._selected_items = all_need_to_selected_items
        self._canvas.event_generate("<<ItemviewSelect>>")

    def identify_item(self, event: tk.Event) -> str:
        x = self._canvas.canvasx(event.x)
        y = self._canvas.canvasy(event.y)
        clicked_item = ""
        for item in self._results:
            item_x, item_y = self._get_item_position(item)
            if (item_x <= x <= item_x + self._thumbnail_size and
                item_y <= y <= item_y + self._thumbnail_size):
                clicked_item = item
                break
        return clicked_item

    def bind(self, sequence: str, func) -> None:
        self._canvas.bind(sequence, func)

    def destroy(self) -> None:
        self._is_destroy = True
        self._cancel_timer()
        self._image_loader.stop()
        self._scrollbar.destroy()
        self._canvas.destroy()
