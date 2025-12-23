import tkinter as tk
from tkinter.ttk import Style, Treeview, Scrollbar
from typing import Callable
from dataclasses import dataclass
from collections import namedtuple
from pathlib import Path
from threading import Thread
import math
from queue import Queue
import datetime
import os



from PIL import Image, ImageTk, ImageOps, UnidentifiedImageError


PreviewResult = namedtuple("PreviewResult", ["image_path", "similarity"])


@dataclass
class Config:
    THUMBNAIL_SIZE: int = 110
    GRID_SPACING: int = 10
    MARGIN: int = 10
    MAX_THREADS: int = 8
    CACHE_SIZE: int = 300
    PRELOAD_ROWS: int = 3
    HIGHLIGHT_COLOR: str = "#2196F3"



class ImageLoader:
    def __init__(self):
        self.task_queue = Queue()
        self.result_queue = Queue()
        self.threads = []
        self.running = True
        
        for i in range(Config.MAX_THREADS):
            thread = Thread(target=self._worker, daemon=True)
            thread.start()
            self.threads.append(thread)
    
    def add_task(self, image_path: str, thumbnail_size: int):
        """添加加载任务"""
        self.task_queue.put((image_path, thumbnail_size))
    
    def _worker(self):
        """工作线程函数"""
        while self.running:
            try:
                image_path, thumbnail_size = self.task_queue.get(timeout=1)
                
                try:
                    # 使用PIL加载图像
                    with Image.open(image_path) as img:
                        # 获取图像信息
                        width, height = img.size
                        
                        # 计算缩略图大小（保持宽高比）
                        img.thumbnail((thumbnail_size, thumbnail_size))
                        
                        # 转换为RGB格式
                        if img.mode in ('RGBA', 'LA', 'P'):
                            # 创建白色背景
                            background = Image.new('RGB', img.size, (255, 255, 255))
                            if img.mode == 'RGBA':
                                # 合并RGBA到RGB
                                background.paste(img, mask=img.split()[-1])
                            else:
                                background.paste(img)
                            img = background
                        elif img.mode != 'RGB':
                            img = img.convert('RGB')
                        
                        # 转换为PhotoImage
                        photo = ImageTk.PhotoImage(img)
                        
                        # 将结果放入结果队列
                        self.result_queue.put({
                            'path': image_path,
                            'photo': photo,
                            'size': (width, height),
                            'thumbnail_size': img.size
                        })
                        
                except Exception as e:
                    print(f"Failed to load image {image_path}: {e}")
                    self.result_queue.put({
                        'path': image_path,
                        'photo': None,
                        'size': (0, 0),
                        'thumbnail_size': (0, 0),
                        'error': str(e)
                    })
                    
                finally:
                    self.task_queue.task_done()
                    
            except:
                continue
    
    def get_results(self):
        """获取加载结果"""
        results = []
        while not self.result_queue.empty():
            results.append(self.result_queue.get_nowait())
        return results
    
    def stop(self):
        """停止加载器"""
        self.running = False
        for thread in self.threads:
            thread.join(timeout=1)




class BasicPreviewView(object):
    def insert_result(self, result: PreviewResult) -> str:
        return ""

    def get_show_results(self) -> list[PreviewResult]:
        return []

    def clear_results(self) -> None:
        pass

    def selection(self) -> tuple[str, ...]:
        return ()

    def selection_set(self, *items: str) -> None:
        pass

    def identify_item(self, event: tk.Event) -> str:
        return ""

    def item(self, item) -> PreviewResult:
        return PreviewResult("", "")

    def bind(self, sequence: str, func: Callable) -> None:
        pass

    def destroy(self) -> None:
        pass



class PreviewCanvasView(BasicPreviewView):
    def __init__(self, parent) -> None:
        super().__init__()
        self.__canvas = self._create_canvas(parent)
        self.__image_path: str = ""
        self.__imagetk = None

    def _create_canvas(self, parent) -> tk.Canvas:
        canvas = tk.Canvas(parent, highlightthickness=0, cursor="hand2")
        canvas.place(relx=0, rely=0, relwidth=1, relheight=1)
        return canvas

    def insert_result(self, image_path: str, image_obj: Image.Image) -> str:
        canvas_width = max(self.__canvas.winfo_width(), 100)
        canvas_height = max(self.__canvas.winfo_height(), 80)
        x = canvas_width // 2
        y = canvas_height // 2
        try:
            img: Image.Image = ImageOps.exif_transpose(image_obj)
            img.thumbnail((canvas_width, canvas_height), Image.Resampling.BICUBIC)
            self.__imagetk = ImageTk.PhotoImage(img)
            self.__image_path = image_path
        except UnidentifiedImageError:
            return ""
        self.__canvas.delete(tk.ALL)
        self.__canvas.create_image(x, y, anchor=tk.CENTER, image=self.__imagetk)
        return self.__image_path

    def selection(self) -> tuple[str, ...]:
        return (self.__image_path, )
    
    def identify_item(self, event: tk.Event) -> str:
        return self.__image_path

    def bind(self, sequence: str, func: Callable) -> None:
        self.__canvas.bind(sequence, func)

    def destroy(self) -> None:
        self.__canvas.destroy()




class DetailListView(BasicPreviewView):
    def __init__(self, parent: tk.Widget) -> None:
        super().__init__()
        self.__treeview = self._create_treeview(parent)
        self.__scrollbar = self._create_scrollbar()
        self.__column_idx_map = {column: idx for idx, column in enumerate(self.__treeview["columns"])}
        self._bind_event()

    def _create_treeview(self, parent) -> Treeview:
        columns = {"名称":160, "大小":100, "修改时间": 160 , "相似度":100}
        result_table = Treeview(parent, show="headings", columns=list(columns))
        for text, width in columns.items():
            result_table.heading(text, text=text, anchor='center')
            result_table.column(text, anchor='center', width=width, stretch=True)
        
        result_table.place(relx=0, rely=0, relwidth=1, relheight=1)
        return result_table

    def _create_scrollbar(self) -> Scrollbar:
        v_scrollbar = Scrollbar(self.__treeview, orient="vertical", cursor="hand2")
        v_scrollbar.pack(fill="both", side="right", padx=2, pady=2)
        return v_scrollbar
    
    def _bind_event(self) -> None:
        self.__scrollbar.config(command=self.__treeview.yview)
        self.__treeview.configure(yscrollcommand=self.__scrollbar.set)
        for column in self.__treeview["columns"]:
            self.__treeview.heading(column, command=lambda column=column: self._sort_column(column, False))

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

    def insert_result(self, result: PreviewResult) -> str:
        image_path = result.image_path
        mtime = datetime.datetime.fromtimestamp(os.path.getmtime(image_path))
        content = (
            os.path.basename(image_path),
            f"{os.path.getsize(image_path) / 1024 / 1024:.2f}MB",
            mtime.strftime("%Y-%m-%d %H:%M:%S"),
            f"{result.similarity:.2f}%"
        )
        return self.__treeview.insert('', tk.END, values=content, iid=image_path)

    def get_show_results(self) -> list[PreviewResult]:
        return [self.item(i) for i in self.__treeview.get_children("")]
            
    def clear_results(self) -> None:
        self.__treeview.delete(*self.__treeview.get_children())
    
    def selection(self) -> tuple[str, ...]:
        return self.__treeview.selection()
    
    def selection_set(self, *items: str) -> None:
        if len(items) == 0:
            return
        if items[0] == tk.ALL:
            self.__treeview.selection_set(*self.__treeview.get_children(""))
        else:
            self.__treeview.selection_set(items)
    
    def identify_item(self, event: tk.Event) -> str:
        return self.__treeview.identify_row(event.y)
    
    def item(self, item: str) -> PreviewResult:
        values = self.__treeview.item(item, "values")
        similarity = float(values[self.__column_idx_map["相似度"]].replace("%", ""))
        return PreviewResult(item, similarity)

    def bind(self, sequence: str, func: Callable) -> None:
        if sequence == "<<ItemviewSelect>>":
            sequence = "<<TreeviewSelect>>"
        self.__treeview.bind(sequence, func)

    def destroy(self) -> None:
        self.__scrollbar.destroy()
        self.__treeview.destroy()



class ThumbnailGridView(BasicPreviewView):
    def __init__(self, parent) -> None:
        super().__init__()
        self.parent = parent
        self.__results: list[PreviewResult] = []
        self.__visible_image_data: dict[str, dict] = {}
        self.loading_tasks: set = set()
        self.font_color = self.get_parent_font_color()
        
        self.__canvas = self._create_canvas(parent)
        self.__scrollbar = self._create_scrollbar()
        self.image_loader = ImageLoader()
        
        self.__cols = 0
        self.__canvas_items: dict[str, dict] = {}  # path -> {image_id, text_id, border_id, result}
        self.visible_items: set = set()
        
        # 选择功能
        self.__selected_items: set[str] = set()  # 存储选中的图片路径
        self.selection_border_items: dict[str, int] = {}  # path -> border_id
        
        # 定时器
        self.after_id = None
        self.scroll_timer = None
        self.scrollbar_drag_timer = None

        self._is_scrollbar_dragging = False
        
        self._bind_event()
        self._start_checking_results()

    def _create_canvas(self, parent: tk.Widget) -> tk.Canvas:
        canvas = tk.Canvas(parent, highlightthickness=0)
        canvas.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)
        canvas.configure(takefocus=1)
        canvas.focus_set()
        return canvas

    def _create_scrollbar(self) -> Scrollbar:
        v_scrollbar = Scrollbar(self.__canvas, orient="vertical", cursor="hand2")
        v_scrollbar.grid(row=0, column=1, sticky="ns", padx=2, pady=2)
        self.__canvas.grid_columnconfigure(0, weight=1)
        self.__canvas.grid_rowconfigure(0, weight=1)
        return v_scrollbar

    def _bind_event(self) -> None:
        self.__scrollbar.config(command=self._on_scrollbar_scroll)
        self.__canvas.configure(yscrollcommand=self.__scrollbar.set)
        self.__scrollbar.bind("<B1-Motion>", self._on_scrollbar_drag)
        self.__scrollbar.bind("<ButtonRelease-1>", self._on_scrollbar_release)
        self.__canvas.bind("<Configure>", self._on_canvas_configure)
        self.__canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.__canvas.bind("<Button-4>", self._on_mousewheel)  # Linux
        self.__canvas.bind("<Button-5>", self._on_mousewheel)  # Linux
        self.__canvas.bind("<Button-1>", self._on_canvas_click)

    def _set_item_selected(self, item: str, selected: bool) -> None:
        if not selected:
            border_id = self.selection_border_items.pop(item, None)
            if border_id and self.__canvas.type(border_id):
                self.__canvas.delete(border_id)
                return
        if item in self.selection_border_items:
            return
        for idx, result in enumerate(self.__results):
            if result.image_path != item:
                continue
            x, y = self._get_item_position(idx)
            border_id = self.__canvas.create_rectangle(
                x - 4, y - 4,
                x + Config.THUMBNAIL_SIZE + 4,
                y + Config.THUMBNAIL_SIZE + 4,
                outline=Config.HIGHLIGHT_COLOR,
                width=2,
                tags=("selection_border", f"path_{item}")
            )
            self.selection_border_items[item] = border_id
            self.__canvas.tag_raise(border_id)
            break

    def _on_scrollbar_scroll(self, *args) -> None:
        if len(args) == 2:
            self.__canvas.yview(*args)
        else:
            self.__canvas.xview(*args)
        self._schedule_load()
    
    def _on_scrollbar_drag(self, event) -> None:
        self._is_scrollbar_dragging = True
        if self.scrollbar_drag_timer:
            self.parent.after_cancel(self.scrollbar_drag_timer)
        self.scrollbar_drag_timer = self.parent.after(100, self._on_scrollbar_drag_update)
    
    def _on_scrollbar_drag_update(self) -> None:
        if self._is_scrollbar_dragging:
            self._load_visible_images()
            self.scrollbar_drag_timer = self.parent.after(100, self._on_scrollbar_drag_update)
    
    def _on_scrollbar_release(self, event) -> None:
        self._is_scrollbar_dragging = False
        if self.scrollbar_drag_timer:
            self.parent.after_cancel(self.scrollbar_drag_timer)
            self.scrollbar_drag_timer = None
        self._schedule_load()
    
    def _schedule_load(self) -> None:
        if self.scroll_timer:
            self.parent.after_cancel(self.scroll_timer)
        
        self.scroll_timer = self.parent.after(50, self._load_visible_images)
    
    def _update_layout(self) -> None:
        canvas_width = self.__canvas.winfo_width()
        old_cols = self.__cols
        
        if canvas_width > 0:
            item_width = Config.THUMBNAIL_SIZE + Config.GRID_SPACING
            self.__cols = max(1, (canvas_width - Config.MARGIN * 2) // item_width)
        else:
            self.__cols = 4
        
        if old_cols != self.__cols and old_cols != 0:
            self._reposition_all_items()
        
        rows = math.ceil(len(self.__results) / self.__cols) if self.__cols > 0 else 0
        
        item_width = Config.THUMBNAIL_SIZE + Config.GRID_SPACING
        item_height = Config.THUMBNAIL_SIZE + Config.GRID_SPACING + 30
        
        total_width = max(
            canvas_width,
            self.__cols * item_width + Config.MARGIN * 2
        )
        total_height = rows * item_height + Config.MARGIN * 2
        self.__canvas.configure(scrollregion=(0, 0, total_width, total_height))
    
    def _get_item_position(self, index: int) -> tuple[int, int]:
        if self.__cols == 0:
            return (Config.MARGIN, Config.MARGIN)
        
        row = index // self.__cols
        col = index % self.__cols
        
        item_width = Config.THUMBNAIL_SIZE + Config.GRID_SPACING
        item_height = Config.THUMBNAIL_SIZE + Config.GRID_SPACING + 30
        
        x = col * item_width + Config.MARGIN + Config.GRID_SPACING // 2
        y = row * item_height + Config.MARGIN + Config.GRID_SPACING // 2
        
        return (x, y)
    
    def _reposition_all_items(self) -> None:
        """重新定位所有已创建的项目"""
        for image_path, items in self.__canvas_items.items():
            try:
                # 找到对应的结果
                result = None
                for r in self.__results:
                    if r.image_path == image_path:
                        result = r
                        break
                
                if result is None:
                    continue
                    
                index = self.__results.index(result)
                x, y = self._get_item_position(index)
                
                # 更新图片位置
                if items.get('image_id') and self.__canvas.type(items['image_id']):
                    self.__canvas.coords(
                        items['image_id'],
                        x + Config.THUMBNAIL_SIZE // 2,
                        y + Config.THUMBNAIL_SIZE // 2
                    )
                
                # 更新加载文字位置
                if items.get('text_id') and self.__canvas.type(items['text_id']):
                    self.__canvas.coords(
                        items['text_id'],
                        x + Config.THUMBNAIL_SIZE // 2,
                        y + Config.THUMBNAIL_SIZE // 2
                    )
                
                # 更新文件名位置
                if items.get('filename_id') and self.__canvas.type(items['filename_id']):
                    filename_y = y + Config.THUMBNAIL_SIZE + Config.GRID_SPACING // 2 + 15
                    self.__canvas.coords(
                        items['filename_id'],
                        x + Config.THUMBNAIL_SIZE // 2,
                        filename_y
                    )
                
                # 更新选中边框位置
                if image_path in self.selection_border_items:
                    border_id = self.selection_border_items[image_path]
                    if self.__canvas.type(border_id):
                        self.__canvas.coords(
                            border_id,
                            x - 4, y - 4,
                            x + Config.THUMBNAIL_SIZE + 4,
                            y + Config.THUMBNAIL_SIZE + 4
                        )
                    
            except ValueError:
                continue
    
    def _load_visible_images(self) -> None:
        if not self.__results or self.__cols == 0:
            return
        
        canvas_x1 = self.__canvas.canvasx(0)
        canvas_y1 = self.__canvas.canvasy(0)
        canvas_x2 = canvas_x1 + self.__canvas.winfo_width()
        canvas_y2 = canvas_y1 + self.__canvas.winfo_height()
        
        # 计算可见的行范围
        item_height = Config.THUMBNAIL_SIZE + Config.GRID_SPACING + 30
        
        start_row = max(0, int(canvas_y1 // item_height) - Config.PRELOAD_ROWS)
        end_row = min(
            math.ceil(len(self.__results) / self.__cols),
            int(canvas_y2 // item_height) + Config.PRELOAD_ROWS
        )
        
        new_visible_items = set()
        for row in range(start_row, end_row + 1):
            for col in range(self.__cols):
                index = row * self.__cols + col
                if index < 0 or index >= len(self.__results):
                    continue
                result = self.__results[index]
                image_path = result.image_path
                new_visible_items.add(image_path)
                
                if image_path not in self.__canvas_items:
                    self._create_placeholder(index)
                
                if image_path in self.__visible_image_data and image_path not in self.visible_items:
                    self._update_canvas_item(index)
                
                if (image_path not in self.__visible_image_data and 
                    image_path not in self.loading_tasks):
                    self._load_item_async(image_path)
        self.visible_items = new_visible_items
    
    def _create_placeholder(self, index: int) -> None:
        x, y = self._get_item_position(index)
        image_path = self.__results[index].image_path
        
        if image_path in self.__canvas_items:
            items = self.__canvas_items[image_path]
            if items.get('text_id') and self.__canvas.type(items['text_id']):
                self.__canvas.delete(items['text_id'])
            if items.get('filename_id') and self.__canvas.type(items['filename_id']):
                self.__canvas.delete(items['filename_id'])
            if items.get('image_id') and self.__canvas.type(items['image_id']):
                self.__canvas.delete(items['image_id'])
        
        text_id = self.__canvas.create_text(
            x + Config.THUMBNAIL_SIZE // 2,
            y + Config.THUMBNAIL_SIZE // 2,
            text="加载中...",
            fill=self.font_color,
            font=("Arial", 10),
            tags=("thumbnail_text", f"path_{image_path}")
        )
        
        filename = os.path.basename(image_path)
        if len(filename) > 20:
            filename = filename[:17] + "..."
        
        filename_y = y + Config.THUMBNAIL_SIZE + Config.GRID_SPACING // 2 + 15
        filename_id = self.__canvas.create_text(
            x + Config.THUMBNAIL_SIZE // 2,
            filename_y,
            text=filename,
            font=("Arial", 8),
            fill=self.font_color,
            tags=("filename", f"path_{image_path}")
        )
        
        self.__canvas_items[image_path] = {
            'text_id': text_id,
            'filename_id': filename_id,
            'image_id': None,
            'result': None
        }
    
    def _update_canvas_item(self, index: int) -> None:
        result = self.__results[index]
        if result.image_path not in self.__visible_image_data or result.image_path not in self.__canvas_items:
            return
        
        data = self.__visible_image_data[result.image_path]
        item_data = self.__canvas_items[result.image_path]
        
        try:
            x, y = self._get_item_position(index)
            
            if item_data['image_id'] is not None and self.__canvas.type(item_data['image_id']):
                self.__canvas.delete(item_data['image_id'])
            
            if item_data['text_id'] is not None and self.__canvas.type(item_data['text_id']):
                self.__canvas.delete(item_data['text_id'])
            
            if item_data['filename_id'] is not None and self.__canvas.type(item_data['filename_id']):
                filename = Path(result.image_path).name
                width, height = data.get('size', (0, 0))
                if len(filename) > 8:
                    tip_info = f"{filename[:8]}...\n{width} x {height}"
                else:
                    tip_info = f"{filename}\n{width} x {height}"
                
                filename_y = y + Config.THUMBNAIL_SIZE + Config.GRID_SPACING // 2 + 15
                self.__canvas.coords(
                    item_data['filename_id'],
                    x + Config.THUMBNAIL_SIZE // 2,
                    filename_y
                )
                self.__canvas.itemconfig(item_data['filename_id'], text=tip_info)
            
            if data['photo'] is not None:
                image_id = self.__canvas.create_image(
                    x + Config.THUMBNAIL_SIZE // 2,
                    y + Config.THUMBNAIL_SIZE // 2,
                    image=data['photo'],
                    tags=("thumbnail_image", f"path_{result.image_path}")
                )
                item_data['image_id'] = image_id
            else:
                error_text = self.__canvas.create_text(
                    x + Config.THUMBNAIL_SIZE // 2,
                    y + Config.THUMBNAIL_SIZE // 2,
                    text=f"{data.get('error', '加载失败')[:10]}",
                    font=("Arial", 9),
                    fill="red",
                    tags=("thumbnail_text", f"path_{result.image_path}")
                )
                item_data['text_id'] = error_text
            
            item_data['result'] = result
            
            if result.image_path in self.selection_border_items:
                border_id = self.selection_border_items[result.image_path]
                if self.__canvas.type(border_id):
                    self.__canvas.tag_raise(border_id)
                
        except ValueError:
            if result.image_path in self.__canvas_items:
                del self.__canvas_items[result.image_path]
    
    def _load_item_async(self, item: str) -> None:
        if item in self.loading_tasks:
            return
        self.loading_tasks.add(item)
        self.image_loader.add_task(item, Config.THUMBNAIL_SIZE)
    
    def _start_checking_results(self) -> None:
        def check_results():
            results = self.image_loader.get_results()
            for result in results:
                self._on_image_loaded(result)
            
            self.after_id = self.parent.after(100, check_results)
        
        check_results()
    
    def _on_image_loaded(self, result: dict) -> None:
        image_path = result['path']
        self.loading_tasks.discard(image_path)
        self.__visible_image_data[image_path] = {
            'photo': result['photo'],
            'size': result['size'],
            'thumbnail_size': result['thumbnail_size'],
            'error': result.get('error')
        }

        if image_path not in self.visible_items:
            return
        
        for index, search_result in enumerate(self.__results):
            if image_path == search_result.image_path:
                self._update_canvas_item(index)
                return
    
    def _on_canvas_configure(self, event) -> None:
        if self.scroll_timer:
            self.parent.after_cancel(self.scroll_timer)
        
        self.scroll_timer = self.parent.after(100, self._delayed_resize)
    
    def _delayed_resize(self) -> None:
        self._update_layout()
        self._load_visible_images()
        self.scroll_timer = None
    
    def _on_mousewheel(self, event) -> None:
        """鼠标滚轮事件"""
        # Windows和Mac
        if event.delta:
            delta = int(-1 * (event.delta / 120))
            self.__canvas.yview_scroll(delta, "units")
        # Linux
        elif event.num == 4:
            self.__canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self.__canvas.yview_scroll(1, "units")
        
        # 延迟加载可见图片
        self._schedule_load()
    
    def _on_canvas_click(self, event: tk.Event) -> None:
        self.__canvas.focus_get()
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
                last_selected = list(self.__selected_items)[-1]
                try:
                    last_index = [r.image_path for r in self.__results].index(last_selected)
                    current_index = [r.image_path for r in self.__results].index(clicked_item)
                    start_idx = min(last_index, current_index)
                    end_idx = max(last_index, current_index)
                    for idx in range(start_idx, end_idx + 1):
                        item_path = self.__results[idx].image_path
                        self.__selected_items.add(item_path)
                        self._set_item_selected(item_path, True)
                except ValueError:
                    self.__selected_items.add(clicked_item)
                    self._set_item_selected(clicked_item, True)
        else:
            for path in list(self.__selected_items):
                self._set_item_selected(path, False)
            self.__selected_items.clear()
            
            self.__selected_items.add(clicked_item)
            self._set_item_selected(clicked_item, True)
            self.__canvas.event_generate("<<ItemviewSelect>>")

    def insert_result(self, result: PreviewResult) -> str:
        self.__results.append(result)
        self._update_layout()
        self.parent.after(100, self._load_visible_images)
        return result.image_path

    def get_show_results(self) -> list[PreviewResult]:
        return self.__results[:]

    def clear_results(self) -> None:
        self.__selected_items.clear()
        for border_id in self.selection_border_items.values():
            if self.__canvas.type(border_id):
                self.__canvas.delete(border_id)
        self.selection_border_items.clear()
        
        self.__results.clear()
        self.__visible_image_data.clear()
        self.loading_tasks.clear()
        self.__canvas_items.clear()
        self.visible_items.clear()
        self.__canvas.delete("all")
        
        self._update_layout()

    def selection(self) -> tuple[str, ...]:
        return tuple(self.__selected_items)

    def selection_set(self, *items: str) -> None:
        if not items:
            for path in list(self.__selected_items):
                self._set_item_selected(path, False)
            self.__selected_items.clear()
            return
        
        if items[0] == tk.ALL:
            for item in self.__results:  # 修改：遍历所有结果
                self.__selected_items.add(item.image_path)
                self._set_item_selected(item.image_path, True)
            return
                
        for path in list(self.__selected_items):
            self._set_item_selected(path, False)
        self.__selected_items.clear()

        for item in items:
            preview_result = self.item(item)
            if preview_result.image_path == "":
                continue
            self.__selected_items.add(item)
            self._set_item_selected(item, True)
        self.__canvas.event_generate("<<ItemviewSelect>>")

    def identify_item(self, event: tk.Event) -> str:
        x = self.__canvas.canvasx(event.x)
        y = self.__canvas.canvasy(event.y)
        clicked_item = ""
        for index, result in enumerate(self.__results):
            try:
                item_x, item_y = self._get_item_position(index)

                if (item_x <= x <= item_x + Config.THUMBNAIL_SIZE and
                    item_y <= y <= item_y + Config.THUMBNAIL_SIZE):
                    clicked_item = result.image_path
                    break
            except ValueError:
                continue
        return clicked_item
    
    def item(self, item: str) -> PreviewResult:
        for result in self.__results:
            if result.image_path == item:
                return result
        return PreviewResult("", "")

    def bind(self, sequence: str, func: Callable) -> None:
        self.__canvas.bind(sequence, func)

    def destroy(self) -> None:
        if self.after_id:
            self.parent.after_cancel(self.after_id)
        
        if self.scroll_timer:
            self.parent.after_cancel(self.scroll_timer)
        
        if self.scrollbar_drag_timer:
            self.parent.after_cancel(self.scrollbar_drag_timer)
        
        self.image_loader.stop()
        self.__scrollbar.destroy()
        self.__canvas.destroy()

    def get_parent_font_color(self) -> str:
        style = Style(self.parent)
        try:
            font_color = style.lookup('.', 'foreground')
            return font_color
        except Exception as e:
            return ""


