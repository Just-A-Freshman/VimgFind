from __future__ import annotations

from tkinter import ttk
import tkinter as tk
import os

from PIL import Image, ImageDraw, ImageTk


_PLACEHOLDER = ("__placeholder__",)


class ImageFolderTreeview(ttk.Treeview):
    def __init__(self, parent, accept_exts: set[str] | None = None, **kwargs):
        kwargs.setdefault("show", "tree headings")
        super().__init__(parent, **kwargs)
        self.__build_style()
        self._accept_exts = accept_exts
        self._placeholder_parents: set[str] = set()
        self._collapse_timers: dict[str, str] = {}
        self._last_theme = self._style.theme_use()

        self.column("#0", anchor=tk.W, stretch=True)
        self.heading("#0", text="图库目录")
        self.bind("<<TreeviewOpen>>", self._on_open)
        self.bind("<<TreeviewClose>>", self._on_close)
        self.bind("<Double-1>", self._on_double_click)
        self.bind("<<ThemeChanged>>", self._on_theme_changed)

    def __build_style(self) -> None:
        if not hasattr(self, "_img_open"):
            self._style = getattr(self.master.winfo_toplevel(), "style", None) or ttk.Style()
        rh = self._style.lookup("Treeview", "rowheight")
        rh = int(rh) if rh else 20
        size = max(int((rh - 5) * 0.7), 8)
        indent = max(size + 10, 20)

        fg = self._style.lookup("Treeview", "foreground")
        if not fg or not fg.startswith("#"):
            fg = "#888888"

        el_name = "folder_indicator"
        icon_size = int(size * 0.8)
        if not hasattr(self, "_img_open"):
            self._img_open, self._img_close = self._make_chevron_images(size, fg)
            self._img_folder = self._make_folder_image(icon_size, fg)
            self._img_file = self._make_file_image(icon_size, fg)
            self._img_empty = ImageTk.PhotoImage(Image.new("RGBA", (size, size), 0))
        else:
            new_open, new_close = self._make_chevron_images(size, fg)
            new_folder = self._make_folder_image(icon_size, fg)
            new_file = self._make_file_image(icon_size, fg)
            for old, new in zip(
                (self._img_open, self._img_close, self._img_folder, self._img_file), 
                (new_open, new_close, new_folder, new_file)
            ):
                self._style.tk.call(getattr(old, "_PhotoImage__photo").name, "copy", getattr(new, "_PhotoImage__photo").name, "-compositingrule", "set")
        try:
            self._style.element_create(
                el_name, "image", self._img_close,
                ("user1", "!user2", self._img_open),
                ("user2", self._img_empty),
                sticky=tk.W, width=size, border=0,
            )
        except tk.TclError:
            pass

        self._style.layout("Treeview.Item", [
            ("Treeitem.padding", {
                "sticky": "nswe",
                "children": [
                    (el_name, {"side": "left", "sticky": ""}),
                    ("Treeitem.image", {"side": "left", "sticky": ""}),
                    ("Treeitem.text", {"sticky": "nswe"}),
                ],
            }),
        ])
        self._style.configure("Treeview", indent=indent)

    def _on_theme_changed(self, event):
        current = self._style.theme_use()
        if current == self._last_theme:
            return
        self._last_theme = current
        self.after(10, self.__build_style)

    @staticmethod
    def _make_chevron_images(size: int, color: str):
        scale = 3
        s = size * scale
        pad = max(2, s // 4)
        half = s // 2
        d = (half - pad) // 2

        im = Image.new("RGBA", (s, s), 0)
        ImageDraw.Draw(im).polygon([(pad, half - d), (s - pad, half - d), (half, half + d)], fill=color)
        im_open = ImageTk.PhotoImage(im.resize((size, size), Image.Resampling.LANCZOS))
        im_close = ImageTk.PhotoImage(im.rotate(90, expand=True).resize((size, size), Image.Resampling.LANCZOS))
        return (im_open, im_close)

    @staticmethod
    def _make_folder_image(size: int, color: str):
        scale = 3
        s = size * scale
        pad = max(1, s // 10)
        tab_w = s * 2 // 5
        tab_h = s // 6
        points = [
            (pad, pad + tab_h),
            (pad, pad),
            (pad + tab_w, pad),
            (pad + tab_w + tab_h // 2, pad + tab_h),
            (s - pad, pad + tab_h),
            (s - pad, s - pad),
            (pad, s - pad),
        ]
        im = Image.new("RGBA", (s, s), 0)
        ImageDraw.Draw(im).polygon(points, fill=color)
        return ImageTk.PhotoImage(im.resize((size, size), Image.Resampling.LANCZOS))

    @staticmethod
    def _make_file_image(size: int, color: str):
        scale = 3
        s = size * scale
        pad = max(1, s // 10)

        k = (s - 2 * pad) / 900.0
        x0 = pad - 62 * k
        y0 = pad + ((s - 2 * pad) - 825.0 * k) / 2 - 99.5 * k
        m = lambda x, y: (x0 + x * k, y0 + y * k)

        mask = Image.new("L", (s, s), 0)
        md = ImageDraw.Draw(mask)
        md.rounded_rectangle([*m(62, 99.5), *m(962, 924.5)], radius=int(119 * k), fill=255)
        md.ellipse([*m(242, 277), *m(422, 453)], fill=0)

        pts = [m(420.9, 864.5)]

        def line_to(p):
            pts.append(m(*p))

        def cubic_to(c1, c2, p3, n=24):
            p0, c1, c2, p3 = pts[-1], m(*c1), m(*c2), m(*p3)
            for i in range(1, n + 1):
                t = i / n
                u = 1 - t
                pts.append((
                    u ** 3 * p0[0] + 3 * u * u * t * c1[0] + 3 * u * t * t * c2[0] + t ** 3 * p3[0],
                    u ** 3 * p0[1] + 3 * u * u * t * c1[1] + 3 * u * t * t * c2[1] + t ** 3 * p3[1],
                ))

        line_to((181, 864.5))
        cubic_to((150, 864.5), (124, 835), (122.9, 806.4))
        line_to((122.9, 761.4))
        cubic_to((170, 735), (250, 655), (298.2, 611))
        cubic_to((335, 660), (390, 700), (445, 695))
        cubic_to((540, 688), (655, 555), (782.1, 429))
        cubic_to((839.3, 490.9), (878.7, 532.1), (903, 554.2))
        line_to((903, 805.3))
        cubic_to((901, 838), (875, 864.3), (842.1, 864.3))
        line_to((420.9, 864.5))
        md.polygon(pts, fill=0)

        img = Image.new("RGBA", (s, s), color)  # type:ignore
        img.putalpha(mask)
        return ImageTk.PhotoImage(img.resize((size, size), Image.Resampling.LANCZOS))

    def _prescan(self, iid: str, path: str):
        try:
            with os.scandir(path) as it:
                if any(self._include_entry(e) for e in it):
                    self.insert(iid, tk.END, text="", values=_PLACEHOLDER)
                    self._placeholder_parents.add(iid)
        except (PermissionError, OSError):
            pass

    def _include_entry(self, entry: os.DirEntry) -> bool:
        try:
            if entry.is_dir(follow_symlinks=False):
                return True
        except OSError:
            return False
        if self._accept_exts is None:
            return True
        return os.path.splitext(entry.name)[1].lower() in self._accept_exts

    def _on_open(self, event):
        iid = self.focus()
        timer_id = self._collapse_timers.pop(iid, None)
        if timer_id is not None:
            self.after_cancel(timer_id)
        if iid not in self._placeholder_parents:
            return
        self._placeholder_parents.discard(iid)

        values = self.item(iid, "values")
        if not values or values[0] == _PLACEHOLDER[0]:
            return
        path = values[0]

        for child in self.get_children(iid):
            self.delete(child)

        self._full_scan(iid, path)

    def _on_close(self, event):
        iid = self.focus()
        if not iid or not self.get_children(iid):
            return
        timer_id = self.after(1000, self._collapse_cleanup, iid)
        self._collapse_timers[iid] = timer_id

    def _collapse_cleanup(self, iid: str):
        self._collapse_timers.pop(iid, None)
        for child in self.get_children(iid):
            self.delete(child)
        values = self.item(iid, "values")
        if values and values[0] not in ("", _PLACEHOLDER[0]):
            self.insert(iid, tk.END, text="", values=_PLACEHOLDER)
            self._placeholder_parents.add(iid)

    def _on_double_click(self, event):
        elem = self.identify_element(event.x, event.y)
        if elem == "folder_indicator":
            return
        iid = self.identify_row(event.y)
        if not iid:
            return
        values = self.item(iid, "values")
        if not values or values[0] == _PLACEHOLDER[0]:
            return
        os.startfile(values[0])
        return "break"

    def _full_scan(self, parent_iid: str, path: str):
        dirs = []
        files = []
        for e in os.scandir(path):
            try:
                dirs.append(e) if e.is_dir(follow_symlinks=False) else files.append(e)
            except (OSError, PermissionError):
                continue

        dirs.sort(key=lambda x: x.name.lower())
        files.sort(key=lambda x: x.name.lower())

        for entry in dirs:
            child = self.insert(parent_iid, tk.END, text=f"  {entry.name}", values=(entry.path,), open=False, image=self._img_folder)
            self._prescan(child, entry.path)

        for entry in files:
            if self._accept_exts is not None and os.path.splitext(entry.name)[1].lower() not in self._accept_exts:
                continue
            self.insert(parent_iid, tk.END, text=f"  {entry.name}", values=(entry.path,), image=self._img_file)

    def add_folder(self, abs_path: str) -> str | None:
        if not os.path.isdir(abs_path):
            return None
        iid = self.insert("", tk.END, text=f"  {abs_path}", values=(abs_path,), open=False, image=self._img_folder,)
        self._prescan(iid, abs_path)
        return iid

    def get_folder_paths(self) -> list[str]:
        paths = []
        for child in self.get_children(""):
            v = self.item(child, "values")
            if v and v[0] != _PLACEHOLDER[0]:
                paths.append(v[0])
        return paths
