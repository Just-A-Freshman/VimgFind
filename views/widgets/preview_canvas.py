from __future__ import annotations

import tkinter as tk

from PIL import Image, ImageTk, ImageOps, UnidentifiedImageError
from ttkbootstrap import tooltip

from .base import BasicImagePreviewView
from utils.i18n import _


class PreviewCanvasView(BasicImagePreviewView):
    __slots__ = ("_canvas", "_tooltip")

    def __init__(self, parent) -> None:
        super().__init__(parent)
        self._canvas = self._create_canvas(parent)
        self._tooltip = tooltip.ToolTip(self._canvas, text=_("没有文件"), delay=500, topmost=True)

    def _create_canvas(self, parent) -> tk.Canvas:
        canvas = tk.Canvas(parent, highlightthickness=0, cursor="hand2")
        canvas.place(relx=0, rely=0, relwidth=1, relheight=1)
        return canvas

    def append(self, image_path: str, image_obj: Image.Image) -> str:
        iid = self._generate_unique_path_item(image_path)
        canvas_width = max(self._canvas.winfo_width(), 100)
        canvas_height = max(self._canvas.winfo_height(), 80)
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
        self._canvas.create_image(x, y, anchor=tk.CENTER, image=imgtk)
        self._tooltip.text = image_path
        return iid
    
    def delete(self, *items) -> None:
        self.clear()

    def clear(self) -> None:
        self._results.clear()
        self._canvas.delete(tk.ALL)
        self._tooltip.text = _("没有文件")

    def selection(self) -> tuple[str, ...]:
        return tuple(self._results.keys())

    def identify_item(self, event: tk.Event) -> str:
        return list(self._results.keys())[0] if self._results else ""

    def bind(self, sequence: str, func) -> None:
        self._canvas.bind(sequence, func)

    def destroy(self) -> None:
        self._results.clear()
        self._canvas.destroy()
