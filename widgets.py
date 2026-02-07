import tkinter as tk
from tkinter.ttk import Treeview, Scrollbar
from ttkbootstrap import Style, tooltip
from typing import Callable, Any
from collections import OrderedDict, namedtuple
import math
import hashlib
import os


from PIL import Image, ImageTk, ImageOps, UnidentifiedImageError


from utils import ImageLoader, FileOperation
from setting import WinInfo


ThemeColor = namedtuple("ThemeColor", ["primary", "fg", "selectbg", "inputbg"])
class BasicImagePreviewView(object):
    def __init__(self, parent: tk.Widget) -> None:
        self.parent = parent
        self._results: OrderedDict[str, tuple] = OrderedDict(dict())
        self.theme_color = self._get_theme_colors()

    def _generate_unique_path_item(self, path: str) -> str:
        norm_path = os.path.normpath(path)
        path_item = hashlib.md5(norm_path.encode()).hexdigest()[:16]
        while path_item in self._results:
            path_item += "#"
        return path_item

    def _get_theme_colors(self) -> ThemeColor:
        """
        ttkbootstrap的style.colors是一个类属性，但它的返回类型错误地标注成了列表，
        导致正常访问它的属性IDE会警告，这里多包一层，只是为了获取类型注解
        """
        style = Style()
        style_color = style.colors
        color_attr = [getattr(style_color, field) for field in ThemeColor._fields]
        return ThemeColor(*color_attr)

    def _change_theme(self) -> None:
        self.theme_color = self._get_theme_colors()

    def append_result(self, image_path: str, *extra_info: Any, **kwargs: Any) -> str:
        return self._generate_unique_path_item(image_path)

    def get_show_results(self) -> list[tuple]:
        return list(self._results.values())

    def clear_results(self) -> None:
        pass

    def selection(self) -> tuple[str, ...]:
        return ()

    def selection_set(self, *items: str) -> None:
        pass

    def identify_item(self, event: tk.Event) -> str:
        return ""

    def item(self, item) -> tuple:
        return self._results[item]

    def bind(self, sequence: str, func: Callable) -> None:
        pass

    def destroy(self) -> None:
        pass



class PreviewCanvasView(BasicImagePreviewView):
    def __init__(self, parent) -> None:
        super().__init__(parent)
        self._canvas = self._create_canvas(parent)
        self._tooltip = tooltip.ToolTip(self._canvas, text="没有文件", delay=500)

    def _create_canvas(self, parent) -> tk.Canvas:
        canvas = tk.Canvas(parent, highlightthickness=0, cursor="hand2")
        canvas.place(relx=0, rely=0, relwidth=1, relheight=1)
        return canvas

    def append_result(self, image_path: str, image_obj: Image.Image) -> str:
        iid = self._generate_unique_path_item(image_path)
        canvas_width = max(self._canvas.winfo_width(), 100)
        canvas_height = max(self._canvas.winfo_height(), 80)
        x = canvas_width // 2
        y = canvas_height // 2
        try:
            img: Image.Image = ImageOps.exif_transpose(image_obj)
            img.thumbnail((canvas_width, canvas_height), Image.Resampling.BICUBIC)
            imgtk = ImageTk.PhotoImage(img)
        except UnidentifiedImageError:
            return ""
        self.clear_results()
        self._results[iid] = (image_path, imgtk)
        self._canvas.create_image(x, y, anchor=tk.CENTER, image=imgtk)
        self._tooltip.text = image_path
        return iid
    
    def clear_results(self) -> None:
        self._results.clear()
        self._canvas.delete(tk.ALL)
        self._tooltip.text = "没有文件"

    def selection(self) -> tuple[str, ...]:
        return tuple(self._results.keys())
    
    def identify_item(self, event: tk.Event) -> str:
        return list(self._results.keys())[0] if self._results else ""

    def bind(self, sequence: str, func: Callable) -> None:
        self._canvas.bind(sequence, func)

    def destroy(self) -> None:
        self._results.clear()
        self._canvas.destroy()



class DetailListView(BasicImagePreviewView):
    def __init__(self, parent: tk.Widget, extra_columns: dict[str, int]) -> None:
        super().__init__(parent)
        self._create_treeview(extra_columns)
        self.parent.after(50, self._create_scrollbar)
        
    def _create_treeview(self, extra_columns: dict[str, int]) -> None:
        columns = {"名称":160, **extra_columns}
        self.__treeview = Treeview(self.parent, show="headings", columns=list(columns))
        for text, width in columns.items():
            self.__treeview.heading(text, text=text, anchor='center')
            self.__treeview.column(text, anchor='center', width=width, stretch=True)
        self.__treeview.place(relx=0, rely=0, relwidth=1, relheight=1)
        for column in self.__treeview["columns"]:
            self.__treeview.heading(column, command=lambda column=column: self._sort_column(column, False))

    def _create_scrollbar(self) -> None:
        self.__scrollbar = Scrollbar(self.__treeview, orient="vertical", cursor="hand2")
        self.__scrollbar.pack(fill="both", side="right", padx=2, pady=2)
        self.__scrollbar.config(command=self.__treeview.yview)
        self.__treeview.configure(yscrollcommand=self.__scrollbar.set)
    
    def _get_colomn_idx(self, column) -> int:
        columns: tuple = self.__treeview["columns"]
        return columns.index(column)

    def _sort_column(self, col: str, reverse: bool) -> None:
        data = [(self.__treeview.set(k, col), k) for k in self.__treeview.get_children("")]
        if col == "相似度" or col == "大小":
            data.sort(key = lambda x: f"{x[0]:0>10}", reverse=reverse)
        else:
            data.sort(reverse=reverse)
        for index, (_, k) in enumerate(data):
            self.__treeview.move(k, "", index)
        self.__treeview.heading(col, command=lambda: self._sort_column(col, not reverse))

    def append_result(self, image_path: str, *extra_info: str | int) -> str:
        iid = self._generate_unique_path_item(image_path)
        content = (os.path.basename(image_path), *extra_info)
        self._results[iid] = (image_path, *extra_info)
        return self.__treeview.insert('', tk.END, values=content, iid=iid, text=image_path)
            
    def clear_results(self) -> None:
        self._results.clear()
        self.__treeview.delete(*self.__treeview.get_children())
    
    def selection(self) -> tuple[str, ...]:
        return self.__treeview.selection()
    
    def selection_set(self, *items: str) -> None:
        if not items:
            return
        if items[0] == tk.ALL:
            self.__treeview.selection_set(self.__treeview.get_children(""))
        else:
            self.__treeview.selection_set(items)
    
    def identify_item(self, event: tk.Event) -> str:
        return self.__treeview.identify_row(event.y)

    def bind(self, sequence: str, func: Callable) -> None:
        if sequence == "<<ItemviewSelect>>":
            sequence = "<<TreeviewSelect>>"
        self.__treeview.bind(sequence, func)

    def destroy(self) -> None:
        self.__scrollbar.destroy()
        self.__treeview.destroy()



class ThumbnailGridView(BasicImagePreviewView):
    """
    缩略图网格式绘制类，不提供指定位置插入元素及删除操作
    """
    THUMBNAIL_SIZE: int = WinInfo.TkS(110)
    MARGIN: int = WinInfo.TkS(10)
    FONT_HEGIHT: int = WinInfo.TkS(32)
    PRELOAD_ROWS: int = 3
    def __init__(self, parent: tk.Widget) -> None:
        super().__init__(parent)
        self._create_canvas()
        self.parent.after(50, self._create_scrollbar)

        self._image_loader = ImageLoader()
        self._loading_tasks: set[str] = set()
        self._visible_image_data: dict[str, dict] = {}

        # 记录画布的id项以及索引位置
        self._tooltip = None
        self._canvas_items: dict[str, dict[str, int]] = {}
        self._visible_items: set[str] = set()
        self._selected_items: set[str] = set()
        
        # 定时器
        self._scroll_timer = ""
        self._scrollbar_drag_timer = ""

        self._cols = 0
        self._is_destroy = False
        self._is_scrollbar_dragging = False
        
        self._bind_event()
        self._check_results()
    
    def _create_canvas(self) -> None:
        self._canvas = tk.Canvas(self.parent)
        self._canvas.grid(row=0, column=0, sticky=tk.NSEW, )
        self.parent.grid_rowconfigure(0, weight=1)
        self.parent.grid_columnconfigure(0, weight=1)
        self._canvas.grid_columnconfigure(0, weight=1)
        self._canvas.grid_rowconfigure(0, weight=1)
        self._canvas.configure(
            takefocus=1,
            background=self.theme_color.inputbg,
            highlightthickness=1, 
            highlightbackground=self.theme_color.primary,
            highlightcolor=self.theme_color.primary
        )
        self._canvas.update()

    def _create_scrollbar(self) -> None:
        # 滚动条的初始化格外慢，因此将将其独立出来
        self._scrollbar = Scrollbar(self._canvas, orient=tk.VERTICAL, cursor="hand2")
        self._scrollbar.grid(row=0, column=1, sticky=tk.NS, padx=2, pady=2)
        self._canvas.configure(yscrollcommand=self._scrollbar.set)
        self._scrollbar.config(command=self._on_scrollbar_scroll)
        self._scrollbar.bind("<B1-Motion>", self._on_scrollbar_drag)
        self._scrollbar.bind("<ButtonRelease-1>", self._on_scrollbar_release)

    def _bind_event(self) -> None:
        self._canvas.bind("<Configure>", self._on_canvas_configure)
        self._canvas.bind("<MouseWheel>", self._on_mousewheel)
        self._canvas.bind("<Button-4>", self._on_mousewheel)  # Linux
        self._canvas.bind("<Button-5>", self._on_mousewheel)  # Linux
        self._canvas.bind("<Button-1>", self._on_canvas_click)
        self._canvas.bind("<KeyPress>", self._on_keyboard_click)
        self._canvas.bind("<<ThemeChanged>>", lambda e: self._change_theme())
        self._canvas.bind("<Enter>", lambda e: self._canvas.config(highlightbackground=self.theme_color.primary))
        self._canvas.bind("<Leave>", lambda e: self._canvas.config(highlightbackground=self.theme_color.selectbg))
        self._canvas.bind("<FocusIn>", lambda e: self._canvas.config(highlightthickness=2))
        self._canvas.bind("<FocusOut>", lambda e: self._canvas.config(highlightthickness=1))

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
            highlightthickness=1
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
        # Windows和Mac
        if event.delta:
            delta = int(-1 * (event.delta / 120))
            self._canvas.yview_scroll(delta, "units")
        # Linux
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
        item_y2 = y + self.THUMBNAIL_SIZE + self.FONT_HEGIHT
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

# 分割线------------------------------------------------------------------------------------------------

    def _get_item_index(self, item: str) -> int:
        if item not in self._canvas_items:
            index = next((idx for idx, key in enumerate(self._results) if key == item), -1)
        else:
            index = self._canvas_items[item]["pos_index"]
        return index

    def _create_placeholder(self, item: str) -> None:
        x, y = self._get_item_position(item)
        filename = os.path.basename(self._results[item][0])
        truncate_filename = FileOperation.truncate_filename(filename)
        placeholder_id = self._canvas.create_text(
            x + self.THUMBNAIL_SIZE // 2, y + self.THUMBNAIL_SIZE // 2,
            text=f"图片加载中...", fill=self.theme_color.fg
        )
        image_info_id = self._canvas.create_text(
            x + self.THUMBNAIL_SIZE // 2, 
            y + self.THUMBNAIL_SIZE + self.MARGIN // 2 + self.FONT_HEGIHT // 2,
            text=truncate_filename, fill=self.theme_color.fg
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
        
        self._canvas.delete(canvas_item["placeholder_id"])

        filename = FileOperation.truncate_filename(self._results[item][0])
        width, height = image_data["size"]
        
        tip_info = f"{filename}\n{width} × {height}"
        self._canvas.itemconfig(canvas_item["image_info_id"], text=tip_info)
        
        if image_data['photo'] is not None:
            if "image_id" not in canvas_item:
                image_id = self._canvas.create_image(
                    x + self.THUMBNAIL_SIZE // 2, 
                    y + self.THUMBNAIL_SIZE // 2, 
                    image=image_data['photo']
                )
                canvas_item["image_id"] = image_id
            else:
                self._canvas.itemconfig(canvas_item["image_id"], image=image_data['photo'])
        else:
            self._canvas.itemconfig(canvas_item["placeholder_id"], text=f"{image_data.get('error', '加载失败')[:10]}")

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
            x - 4, y - 4, x + self.THUMBNAIL_SIZE + 4, y + self.THUMBNAIL_SIZE + 4,
            fill=self.theme_color.selectbg
        )
        canvas_item["border_id"] = border_id
        self._canvas.tag_lower(border_id)

    def _update_layout(self) -> None:
        canvas_width = self._canvas.winfo_width()
        canvas_height = self._canvas.winfo_height()
        old_cols = self._cols
        item_width = self.THUMBNAIL_SIZE + self.MARGIN
        self._cols = max(1, (canvas_width - self.MARGIN * 2) // item_width)
        
        if old_cols != self._cols and old_cols != 0:
            for item, canvas_item in self._canvas_items.items():
                x, y = self._get_item_position(item)
                image_id = canvas_item.get("image_id", "")
                if image_id:
                    self._canvas.coords(image_id, x + self.THUMBNAIL_SIZE // 2, y + self.THUMBNAIL_SIZE // 2)

                border_id = canvas_item.get("border_id", "")
                if border_id:
                    self._canvas.coords(border_id, x - 4, y - 4, x + self.THUMBNAIL_SIZE + 4, y + self.THUMBNAIL_SIZE + 4)

                self._canvas.coords(canvas_item["placeholder_id"], x + self.THUMBNAIL_SIZE // 2, y + self.THUMBNAIL_SIZE // 2)
                self._canvas.coords(canvas_item["image_info_id"],  x + self.THUMBNAIL_SIZE // 2, y + self.THUMBNAIL_SIZE + self.MARGIN // 2 + self.FONT_HEGIHT // 2)
        
        rows = math.ceil(len(self._results) / self._cols) if self._cols > 0 else 0
        item_height = self.THUMBNAIL_SIZE + self.MARGIN + self.FONT_HEGIHT
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
        
        item_width = self.THUMBNAIL_SIZE + self.MARGIN
        item_height = self.THUMBNAIL_SIZE + self.MARGIN + self.FONT_HEGIHT
        
        x = col * item_width + self.MARGIN + self.MARGIN // 2
        y = row * item_height + self.MARGIN + self.MARGIN // 2
        
        return (x, y)        
    
    def _load_visible_images(self) -> None:
        if not self._results or self._cols == 0:
            return
        
        canvas_y1 = self._canvas.canvasy(0)
        canvas_y2 = canvas_y1 + self._canvas.winfo_height()
        item_height = self.THUMBNAIL_SIZE + self.MARGIN + 30
        
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
                self._image_loader.add_task(item, image_path, self.THUMBNAIL_SIZE)
        self._visible_items = new_visible_items

# 对外接口--------------------------------------------------------------------------------------------

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
            if (item_x <= x <= item_x + self.THUMBNAIL_SIZE and
                item_y <= y <= item_y + self.THUMBNAIL_SIZE):
                clicked_item = item
                break
        return clicked_item

    def bind(self, sequence: str, func: Callable) -> None:
        self._canvas.bind(sequence, func)

    def destroy(self) -> None:
        self._is_destroy = True
        self._cancel_timer()
        self._image_loader.stop()
        self._scrollbar.destroy()
        self._canvas.destroy()




