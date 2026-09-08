from __future__ import annotations

from typing import TYPE_CHECKING, Callable
import tkinter as tk
import logging

from ttkbootstrap import Style

from config.settings import Setting, TkS
from utils.i18n import _

if TYPE_CHECKING:
    from views.exclude_dialog import ExcludeDialog


class ExcludePreviewController:
    def __init__(self, dialog: ExcludeDialog, setting: Setting, on_rules_changed: Callable[[list[str]], None] | None = None) -> None:
        self.dialog = dialog
        self.setting = setting
        self.__on_rules_changed = on_rules_changed
        self.__rule_entry = None
        self.__edit_lock = False

    def collect_rules(self) -> list[str]:
        rules: list[str] = []
        for child in self.dialog.rules_tree.get_children():
            text = self.dialog.rules_tree.item(child, "values")[0].strip()
            if text:
                rules.append(text)
        return rules

    def on_delete_selected(self) -> None:
        selected = self.dialog.rules_tree.selection()
        if selected:
            self.dialog.rules_tree.delete(*selected)
            self.__notify_rules_changed()

    def on_add_name(self) -> None:
        if self.__edit_lock:
            return
        iid = self.dialog.rules_tree.insert("", tk.END, values=("",))
        self.dialog.rules_tree.yview_moveto(1.0)
        self.__edit_item(iid, "")

    def on_item_double_click(self, event: tk.Event) -> None:
        iid = self.dialog.rules_tree.identify_row(event.y)
        if not iid:
            return
        text = self.dialog.rules_tree.item(iid, "values")[0]
        self.__edit_item(iid, text)

    def load_rules_into_view(self) -> None:
        rules = self.setting.model.index.exclude_rules or []
        for rule in rules:
            self.dialog.rules_tree.insert("", tk.END, values=(rule,))

    def on_save(self) -> None:
        try:
            self.setting.model.index.exclude_rules = self.collect_rules()
            self.setting.save()
            self.__notify_rules_changed()
            self.dialog.destroy()
        except Exception as e:
            logging.error("on_save error: %s", e, exc_info=True)
            try:
                self.dialog.destroy()
            except Exception:
                pass

    def __notify_rules_changed(self) -> None:
        if self.__on_rules_changed:
            self.__on_rules_changed(self.collect_rules())

    def __edit_item(self, iid: str, initial_text: str = "") -> None:
        if self.__rule_entry is not None:
            self.__rule_entry.destroy()

        tree = self.dialog.rules_tree
        tree.selection_remove(*tree.selection())

        tree.update_idletasks()
        item_bbox = tree.bbox(iid, column="name")
        row_height = Style().lookup('Treeview', 'rowheight')
        content_w = tree.winfo_width() - tree.winfo_children()[0].winfo_width()

        if item_bbox:
            ix, iy, _, ih = item_bbox
            entry_x, entry_y, entry_w, entry_h = ix, iy, content_w - ix, ih
        else:
            children = tree.get_children()
            row_idx = children.index(iid)
            entry_x, entry_y = TkS(1), row_idx * row_height
            entry_w, entry_h = content_w - TkS(1), row_height

        entry = tk.Entry(tree, bd=0, highlightthickness=1)
        entry.insert(0, initial_text)
        entry.select_range(0, tk.END)
        entry.icursor(tk.END)
        self.__rule_entry = entry
        self.__edit_lock = True

        _confirming = False
        def on_confirm(event=None):
            nonlocal _confirming
            if _confirming:
                return
            _confirming = True
            text = entry.get().strip()
            if text:
                tree.item(iid, values=(text,))
                tree.selection_set(iid)
                tree.focus(iid)
                self.__notify_rules_changed()
            elif not initial_text:
                tree.delete(iid)
            self.__edit_lock = False
            entry.master.after_idle(lambda e=entry: e.destroy())

        def on_cancel(event=None):
            nonlocal _confirming
            if _confirming:
                return
            _confirming = True
            if not initial_text:
                tree.delete(iid)
            self.__edit_lock = False
            entry.master.after_idle(lambda e=entry: e.destroy())

        entry.place(x=entry_x, y=entry_y, width=entry_w, height=entry_h)
        entry.focus_set()
        entry.bind("<Return>", on_confirm)
        entry.bind("<FocusOut>", on_confirm)
        entry.bind("<Escape>", on_cancel)
