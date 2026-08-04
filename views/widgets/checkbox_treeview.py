from __future__ import annotations

import tkinter as tk
from typing import Callable, Literal

from PIL import Image, ImageDraw, ImageFont, ImageTk
from tkinter.ttk import Treeview
from ttkbootstrap import Scrollbar, Style

from config.settings import TkS

from .drag_treeview import DragReorderTreeview


class CheckboxTreeview(tk.Frame):
    def __init__(self, parent, on_toggle: Callable[[str, bool], None] | None = None, padding: int = 0, **kwargs) -> None:
        super().__init__(parent)
        self.on_toggle: Callable[[str, bool], None] | None = on_toggle
        self.__checked: dict[str, bool] = {}
        self.__off_img: ImageTk.PhotoImage | None = None
        self.__on_img: ImageTk.PhotoImage | None = None
        self.__images_ready = False
        self.__syncing_views = False

        check_w = TkS(30)
        border = self.__get_tree_borderwidth()
        self.__border = border

        self.text_tree = DragReorderTreeview(
            self, show="tree headings", padding=(padding, padding, check_w, padding), **kwargs)
        self.text_tree.on_reorder = self.__sync_check_order

        # 滚动条与复选框列都嵌入文本树内部，先建滚动条以获取其宽度
        self.scrollbar = Scrollbar(self.text_tree, orient=tk.VERTICAL)
        sb_w = self.scrollbar.winfo_reqwidth()
        reserve = check_w + sb_w
        self.text_tree.configure(padding=(padding, padding, reserve, padding))

        self.check_tree = Treeview(
            self.text_tree, style=self.__get_borderless_style(),
            show="tree headings", padding=(0, padding, 0, padding))
        self.check_tree.heading("#0", text="", anchor=tk.CENTER)
        self.check_tree.column("#0", anchor=tk.CENTER, width=check_w, stretch=False)

        self.check_tree.place(relx=1.0, x=-(border + reserve), y=border, width=check_w)
        self.scrollbar.place(relx=1.0, x=-(border + sb_w), y=border, width=sb_w)
        self.text_tree.bind("<Configure>", self.__on_text_configure, add="+")

        self.text_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.check_tree.bind("<Button-1>", self.__on_check_click)
        self.check_tree.bind("<<ThemeChanged>>", self.__on_theme_changed)
        self.text_tree.bind("<<TreeviewSelect>>", lambda _e: self.__sync_check_selection())

        self.text_tree.configure(yscrollcommand=self.__on_yview)
        self.check_tree.configure(yscrollcommand=self.__on_yview)
        self.scrollbar.config(command=self.__on_scrollbar)

    def insert(self, parent, index, *, checked: bool = False, **kwargs):
        iid = self.text_tree.insert(parent, index, **kwargs)
        self.check_tree.insert(parent, index, iid=iid)
        self.__ensure_images()
        self.__checked[iid] = bool(checked)
        self.__apply_image(iid)
        return iid

    def delete(self, *items) -> None:
        for iid in items:
            self.__checked.pop(iid, None)
        self.text_tree.delete(*items)
        self.check_tree.delete(*items)

    def set_checked(self, iid: str, checked: bool) -> None:
        self.__ensure_images()
        self.__checked[iid] = bool(checked)
        self.__apply_image(iid)

    def toggle(self, iid: str) -> None:
        self.set_checked(iid, not self.__checked.get(iid, False))

    def is_checked(self, iid: str) -> bool:
        return self.__checked.get(iid, False)

    def heading(self, *args, **kwargs):
        return self.text_tree.heading(*args, **kwargs)

    def column(self, *args, **kwargs):
        return self.text_tree.column(*args, **kwargs)

    def bind(self, sequence=None, func=None, add: Literal["+", ""] | None="+", **kwargs):
        return self.text_tree.bind(sequence, func, add=add, **kwargs)

    def selection(self, *args, **kwargs):
        return self.text_tree.selection(*args, **kwargs)

    def selection_set(self, *args, **kwargs):
        return self.text_tree.selection_set(*args, **kwargs)

    def focus(self, *args, **kwargs):
        return self.text_tree.focus(*args, **kwargs)

    def see(self, *args, **kwargs):
        result = self.text_tree.see(*args, **kwargs)
        self.__sync_views_from_text()
        return result

    def set(self, *args, **kwargs):
        return self.text_tree.set(*args, **kwargs)

    def item(self, *args, **kwargs):
        return self.text_tree.item(*args, **kwargs)

    def get_children(self, *args, **kwargs):
        return self.text_tree.get_children(*args, **kwargs)

    # ------------------------------------------------------------ 内部实现

    def __on_check_click(self, event: tk.Event):
        if self.check_tree.identify("region", event.x, event.y) != "tree":
            return
        iid = self.check_tree.identify_row(event.y)
        if not iid:
            return
        self.text_tree.focus_set()
        self.__checked[iid] = not self.__checked.get(iid, False)
        self.__apply_image(iid)
        if self.on_toggle:
            self.on_toggle(iid, self.__checked[iid])
        return "break"

    @staticmethod
    def __get_borderless_style() -> str:
        style = Style.get_instance()
        if style is None:
            return "Treeview"
        style.configure("NoBorder.Treeview", borderwidth=0, relief="flat")
        return "NoBorder.Treeview"

    @staticmethod
    def __get_tree_borderwidth() -> int:
        style = Style.get_instance()
        if style is None:
            return 0
        opts = style.configure("Treeview") or {}
        return int(opts.get("borderwidth") or 0)

    def __on_text_configure(self, event: tk.Event) -> None:
        h = event.height - 2 * self.__border
        self.check_tree.place_configure(y=self.__border, height=h)
        self.scrollbar.place_configure(y=self.__border, height=h)

    def __sync_check_selection(self) -> None:
        self.check_tree.selection_set(self.text_tree.selection())
        self.__sync_views_from_text()

    def __sync_views_from_text(self) -> None:
        first, last = self.text_tree.yview()
        self.check_tree.yview_moveto(first)
        self.scrollbar.set(first, last)

    def __sync_check_order(self, source_idx: int, target_idx: int) -> None:
        for new_idx, iid in enumerate(self.text_tree.get_children()):
            self.check_tree.move(iid, "", new_idx)

    def __on_yview(self, first: float, last: float) -> None:
        self.scrollbar.set(first, last)
        if self.__syncing_views:
            return
        self.__syncing_views = True
        try:
            self.text_tree.yview_moveto(first)
            self.check_tree.yview_moveto(first)
        finally:
            self.__syncing_views = False

    def __on_scrollbar(self, *args) -> None:
        self.text_tree.yview(*args)
        self.check_tree.yview(*args)

    def __ensure_images(self) -> None:
        if not self.__images_ready:
            self.__build_images()

    def __build_images(self) -> None:
        style = Style.get_instance()
        if style is None:
            self.__off_img = None
            self.__on_img = None
            self.__images_ready = True
            return
        colors = style._get_builder().colors
        self.__off_img, self.__on_img = self.__create_check_images(colors)
        self.__images_ready = True

    @staticmethod
    def __create_check_images(colors):
        SS = 4
        base = 134 * SS
        box = TkS(14)

        def hex2rgb(h: str):
            h = h.lstrip("#")
            return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

        primary = hex2rgb(colors.get("primary"))
        fg, bg = hex2rgb(colors.fg), hex2rgb(colors.bg)
        selectfg = hex2rgb(colors.selectfg)

        def blend(a_color, b_color, alpha):
            return tuple(int(alpha * c1 + (1 - alpha) * c2) for c1, c2 in zip(a_color, b_color))

        off_border = blend(fg, bg, 0.4)

        off_sub = Image.new("RGBA", (base, base))
        d = ImageDraw.Draw(off_sub)
        d.rounded_rectangle([2 * SS, 2 * SS, 132 * SS, 132 * SS], radius=16 * SS,
                            outline=off_border, width=6 * SS, fill=bg)
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
        return ImageTk.PhotoImage(off), ImageTk.PhotoImage(on)

    def __apply_image(self, iid: str) -> None:
        if self.__on_img is None or self.__off_img is None:
            return
        checked = self.__checked.get(iid, False)
        self.check_tree.item(iid, image=self.__on_img if checked else self.__off_img)

    def __on_theme_changed(self, event: tk.Event) -> None:
        self.__build_images()
        for iid in self.check_tree.get_children():
            self.__apply_image(iid)
