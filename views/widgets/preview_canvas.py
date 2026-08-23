from __future__ import annotations

from typing import Callable, Literal
from pathlib import Path
import tkinter as tk

from PIL import Image, ImageTk, ImageOps, UnidentifiedImageError
from ttkbootstrap.widgets import ToolTip

from .base import BasicImagePreviewView
from utils.i18n import _
import utils.image_ops as image_ops
from tkinterdnd2 import DND_FILES


class PreviewCanvasView(tk.Canvas, BasicImagePreviewView):
    __slots__ = ("__tooltip", "__resize_timer")

    def __init__(self, master) -> None:
        tk.Canvas.__init__(self, master, highlightthickness=0, cursor="hand2")
        BasicImagePreviewView.__init__(self, master)
        self.pack(fill=tk.BOTH, expand=True)
        self.bind('<Configure>', self.__on_configure)
        self.__tooltip = ToolTip(self, text=_("没有文件"), delay=500, topmost=True)
        self.__resize_timer: str = ""

    def __on_configure(self, event: tk.Event) -> None:
        if not self._results:
            return
        image_path, imgtk = self._results[self.identify_item(event)]
        self.coords(self.find_all()[0], event.width // 2, event.height // 2)
        if imgtk.width() == max(event.width, 100) or imgtk.height() == max(event.height, 80):
            return
        self.clear()
        self.append(image_path, ImageTk.getimage(imgtk))
        if self.__resize_timer:
            self.after_cancel(self.__resize_timer)
        self.__resize_timer = tk.Canvas.after(self, 500, lambda: self.clear() or self.append(image_path))

    def append(self, image_path: Path, image_obj: Image.Image | None = None) -> str:
        if self.__resize_timer:
            self.after_cancel(self.__resize_timer)
        iid = self.generate_path_item(image_path, unique=False)
        if len(self.selection()) != 0 and iid == self.selection()[0]:
            return iid
        canvas_width = max(self.winfo_width(), 100)
        canvas_height = max(self.winfo_height(), 80)
        x = canvas_width // 2
        y = canvas_height // 2
        try:
            if image_obj is None:
                image_obj = image_ops.parse_image_from_path(image_path)
            img: Image.Image = ImageOps.exif_transpose(image_obj)    # type: ignore[arg-type]
            img = ImageOps.contain(img, (canvas_width, canvas_height), Image.Resampling.LANCZOS)
            imgtk = ImageTk.PhotoImage(img)
        except UnidentifiedImageError:
            return ""
        self.clear()
        self._results[iid] = (image_path, imgtk)
        self.create_image(x, y, anchor=tk.CENTER, image=imgtk)
        self.__tooltip.text = str(image_path.resolve())
        return iid
    
    def delete(self, *items) -> None:
        self.clear()

    def clear(self) -> None:
        self._results.clear()
        tk.Canvas.delete(self, tk.ALL)
        self.__tooltip.text = _("没有文件")

    def selection(self) -> tuple[str, ...]:
        return tuple(self._results.keys())

    def identify_item(self, event: tk.Event) -> str:
        return list(self._results.keys())[0] if self._results else ""

    def bind(self, sequence: str | None = None, func: Callable | None = None, add: bool | Literal['', '+'] | None = None):    # type: ignore
        tk.Canvas.bind(self, sequence, func, add)

    def destroy(self) -> None:
        if self.__resize_timer:
            self.after_cancel(self.__resize_timer)
        self._results.clear()
        tk.Canvas.destroy(self)
