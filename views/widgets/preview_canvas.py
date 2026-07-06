from ttkbootstrap import tooltip, Toplevel, Label
import tkinter as tk

from PIL import Image, ImageTk, ImageOps, UnidentifiedImageError

from .base import BasicImagePreviewView


class TransientToolTip(tooltip.ToolTip):
    def show_tip(self, *_):
        if self.toplevel:
            return
        x = self.widget.winfo_pointerx() + 25
        y = self.widget.winfo_pointery() + 10
        self.toplevel = Toplevel(**self.toplevel_kwargs)
        self.toplevel.attributes('-topmost', True)
        self.toplevel.geometry(f"+{x}+{y}")
        lbl = Label(
            master=self.toplevel,
            text=self.text,
            justify=tk.LEFT,
            wraplength=self.wraplength,   # type:ignore
            padding=10,
        )
        lbl.pack(fill=tk.BOTH, expand=True)
        if self.bootstyle:
            lbl.configure(style=self.bootstyle)
        else:
            lbl.configure(style="tooltip.TLabel")


class PreviewCanvasView(BasicImagePreviewView):
    def __init__(self, parent) -> None:
        super().__init__(parent)
        self._canvas = self._create_canvas(parent)
        self._tooltip = TransientToolTip(self._canvas, text="没有文件", delay=500)

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
            img: Image.Image = ImageOps.exif_transpose(image_obj)    # type:ignore
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

    def bind(self, sequence: str, func) -> None:
        self._canvas.bind(sequence, func)

    def destroy(self) -> None:
        self._results.clear()
        self._canvas.destroy()
