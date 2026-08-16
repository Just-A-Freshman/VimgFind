from __future__ import annotations

from typing import Callable, Literal
from pathlib import Path
import tkinter as tk

from PIL import Image, ImageTk, ImageOps, UnidentifiedImageError
from ttkbootstrap.widgets import ToolTip

from .base import BasicImagePreviewView
from utils.i18n import _
import utils.image_ops as image_ops


class PreviewCanvasView(tk.Canvas, BasicImagePreviewView):
    __slots__ = ("__tooltip", )

    def __init__(self, master) -> None:
        tk.Canvas.__init__(self, master, highlightthickness=0, cursor="hand2")
        BasicImagePreviewView.__init__(self, master)
        self.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.bind('<Configure>', self.__on_configure)
        self.__tooltip = ToolTip(self, text=_("没有文件"), delay=500, topmost=True)
        self.__resize_timer: str = ""

    def __on_configure(self, event: tk.Event) -> None:
        if not self._results:
            return
        imaga_path, imgtk = self._results[self.identify_item(event)]
        if abs(max(self.winfo_width(), 100) - imgtk.width()) < 10 or abs(max(self.winfo_height(), 80) - imgtk.height()) < 10:
            self.coords(self.find_all()[0], self.winfo_width() // 2, self.winfo_height() // 2)
            return
        if self.__resize_timer:
            self.after_cancel(self.__resize_timer)
        self.__resize_timer = tk.Canvas.after(self, 500, lambda: self.clear() or self.append(imaga_path))

    def append(self, image_path: Path, image_obj: Image.Image | None = None) -> str:
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
            img.thumbnail((canvas_width, canvas_height), Image.Resampling.LANCZOS)
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
        self._results.clear()
        tk.Canvas.destroy(self)
