from __future__ import annotations

from typing import Callable, Literal
from pathlib import Path
import tkinter as tk

from PIL import Image, ImageTk, ImageOps, UnidentifiedImageError

from .base import BasicImagePreviewView
from .tooltip import TopmostToolTip
from utils.i18n import _


class PreviewCanvasView(tk.Canvas, BasicImagePreviewView):
    __slots__ = ("__tooltip", )

    def __init__(self, master) -> None:
        tk.Canvas.__init__(self, master, highlightthickness=0, cursor="hand2")
        BasicImagePreviewView.__init__(self, master)
        self.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.__tooltip = TopmostToolTip(self, text=_("没有文件"), delay=500, topmost=True)

    def append(self, image_path: Path, image_obj: Image.Image) -> str:
        iid = self.generate_path_item(image_path, unique=False)
        if len(self.selection()) != 0 and iid == self.selection()[0]:
            return iid
        canvas_width = max(self.winfo_width(), 100)
        canvas_height = max(self.winfo_height(), 80)
        x = canvas_width // 2
        y = canvas_height // 2
        try:
            img: Image.Image = ImageOps.exif_transpose(image_obj)    # type: ignore[arg-type]
            img.thumbnail((canvas_width, canvas_height), Image.Resampling.BICUBIC)
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
