from __future__ import annotations

import tkinter as tk
from tkinter.ttk import Treeview
from tkinter.font import Font
from typing import Callable, Literal

from PIL import Image, ImageDraw, ImageFont, ImageTk
from ttkbootstrap import Scrollbar, Style
from ttkbootstrap.colorutils import color_to_rgb

from config.settings import TkS, WinInfo
from .drag_treeview import DragReorderTreeview


class CheckboxTreeview(DragReorderTreeview):
    def __init__(self, parent, checkbox_name = "", padding: int = 0, **kwargs) -> None:
        super().__init__(parent, show="tree headings", **kwargs)
        self.__checked: dict[str, bool] = {}
        self.__off_img: ImageTk.PhotoImage | None = None
        self.__on_img: ImageTk.PhotoImage | None = None
        
        self.__images_ready = False
        self.__syncing_views = False
        self.__reserve = self.__border = 0
        
        self.check_tree = Treeview(self, show="tree headings", style="NoBorder.Treeview")
        self.scrollbar = Scrollbar(self, orient=tk.VERTICAL)
        self.__env_init(padding, checkbox_name)

    def __env_init(self, padding: int, checkbox_name: str = "") -> None:
        scrollbar_width = self.scrollbar.winfo_reqwidth()
        checkbox_width = max(Font(font=WinInfo.default_font).measure(checkbox_name) + scrollbar_width, TkS(35))
        self.__reserve = checkbox_width + scrollbar_width
        self.__border = TkS(1)

        self.check_tree.heading("#0", text=checkbox_name, anchor=tk.W)
        self.check_tree.column("#0", anchor=tk.W)
        
        self.check_tree.place(relx=1.0, x=-(self.__border + self.__reserve), y=self.__border, width=checkbox_width)
        self.scrollbar.place(relx=1.0, x=-(self.__border + scrollbar_width), y=self.__border, width=scrollbar_width)
        self.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.check_tree.bind("<Button-1>", self.__on_check_click)
        self.check_tree.bind("<<ThemeChanged>>", self.__on_theme_changed)
        self.bind("<Configure>", lambda e: self.__reposition(), add="+")
        self.bind("<<TreeviewSelect>>", lambda e: self.check_tree.selection_set(self.selection()), add="+")

        self.config(on_reorder=lambda source, target: self.check_tree.move(self.check_tree.get_children("")[source], "", target))
        self.configure(padding=(padding, padding, self.__reserve, padding), yscrollcommand=self.__on_yview)
        self.check_tree.configure(yscrollcommand=self.__on_yview, padding=(0, padding, 0, padding))
        self.scrollbar.config(command=lambda *args: self.yview(*args) or self.check_tree.yview(*args))

    def config(self, *args, on_toggle: Callable[[str, bool], None] | None = None, **kwargs):
        if on_toggle is not None:
            self.__on_toggle = on_toggle
        DragReorderTreeview.config(self, *args, **kwargs)

    def insert(self, parent, index, *, checked: bool = False, **kwargs) -> str:  # type:ignore
        iid = DragReorderTreeview.insert(self, parent, index, **kwargs)
        self.check_tree.insert(parent, index, iid=iid)
        if not self.__images_ready:
            self.__build_images()
        self.__checked[iid] = bool(checked)
        self.__apply_image(iid)
        return iid

    def delete(self, *items: str) -> None:   # type: ignore
        for iid in items:
            self.__checked.pop(iid, None)
        self.delete(*items)
        self.check_tree.delete(*items)

    def set_checked(self, iid: str, checked: bool) -> None:
        if not self.__images_ready:
            self.__build_images()
        self.__checked[iid] = bool(checked)
        self.__apply_image(iid)

    def toggle(self, iid: str) -> None:
        self.set_checked(iid, not self.__checked.get(iid, False))

    def is_checked(self, iid: str) -> bool:
        return self.__checked.get(iid, False)

    def __on_check_click(self, event: tk.Event):
        if self.check_tree.identify("region", event.x, event.y) != "tree":
            return
        iid = self.check_tree.identify_row(event.y)
        if not iid:
            return
        self.focus_set()
        self.__checked[iid] = not self.__checked.get(iid, False)
        self.__apply_image(iid)
        if self.__on_toggle:
            self.__on_toggle(iid, self.__checked[iid])
        return "break"

    def __reposition(self) -> None:
        h = self.winfo_height() - 2 * self.__border
        self.check_tree.place_configure(relx=1, x=-(self.__border + self.__reserve), y=self.__border, height=h)
        self.scrollbar.place_configure(relx=1, x=-(self.__border + self.scrollbar.winfo_reqwidth()), y=self.__border, height=h)

    def __on_yview(self, first: float, last: float) -> None:
        self.scrollbar.set(first, last)
        if self.__syncing_views:
            return
        self.__syncing_views = True
        try:
            self.yview_moveto(first)
            self.check_tree.yview_moveto(first)
        finally:
            self.__syncing_views = False

    def __build_images(self) -> None:
        style = Style.get_instance()
        if style is None:
            self.__off_img = None
            self.__on_img = None
            self.__images_ready = True
            return
        
        SS = 4
        base = 134 * SS
        box = TkS(14)
        style = Style()
        primary = color_to_rgb(style.colors.get("primary"))     # type: ignore
        fg, bg = color_to_rgb(style.colors.get("fg")), color_to_rgb(style.colors.get("bg"))    # type: ignore
        selectfg = color_to_rgb(style.colors.get("selectfg"))       # type: ignore

        off_border = tuple(int(0.4 * c1 + 0.6 * c2) for c1, c2 in zip(fg, bg))   # type:ignore
        off_sub = Image.new("RGBA", (base, base))
        d = ImageDraw.Draw(off_sub)
        d.rounded_rectangle([2 * SS, 2 * SS, 132 * SS, 132 * SS], radius=16 * SS, outline=off_border, width=6 * SS, fill=bg)
        on_sub = Image.new("RGBA", (base, base))
        d = ImageDraw.Draw(on_sub)
        d.rounded_rectangle(
            [2 * SS, 2 * SS, 132 * SS, 132 * SS], radius=16 * SS,
            fill=primary, outline=primary, width=3 * SS
        )
        try:
            fnt = ImageFont.truetype("seguisym.ttf", 120 * SS)
        except OSError:
            fnt = ImageFont.load_default()
        
        d.text((20 * SS, -20 * SS), "✓", font=fnt, fill=selectfg)
        resize = Image.Resampling.LANCZOS
        off_sub = off_sub.resize((box, box), resize)
        on_sub = on_sub.resize((box, box), resize)
        x0 = TkS(3)
        canvas_w = x0 + box
        off = Image.new("RGBA", (canvas_w, box))
        off.paste(off_sub, (x0, 0), off_sub)
        on = Image.new("RGBA", (canvas_w, box))
        on.paste(on_sub, (x0, 0), on_sub)
        self.__off_img = ImageTk.PhotoImage(off)
        self.__on_img = ImageTk.PhotoImage(on)
        self.__images_ready = True

    def __apply_image(self, iid: str) -> None:
        if self.__on_img is None or self.__off_img is None:
            return
        checked = self.__checked.get(iid, False)
        self.check_tree.item(iid, image=self.__on_img if checked else self.__off_img)

    def __on_theme_changed(self, event: tk.Event) -> None:
        self.check_tree.configure(style="NoBorder.Treeview")
        self.__build_images()
        for iid in self.check_tree.get_children():
            self.__apply_image(iid)
