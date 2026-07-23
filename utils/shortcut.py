import tkinter as tk

MODIFIER_KEYS: dict[str, str] = {
    "Control_L": "Ctrl", "Control_R": "Ctrl",
    "Shift_L": "Shift", "Shift_R": "Shift",
    "Alt_L": "Alt", "Alt_R": "Alt",
    "Super_L": "Win", "Super_R": "Win",
}

SPECIAL_KEYS: dict[str, str] = {
    "Return": "Enter",
    "space": "Space",
    "Tab": "Tab",
    "Escape": "Esc",
    "BackSpace": "Backspace",
    "Delete": "Delete",
    "minus": "-",
    "equal": "=",
    "semicolon": ";",
    "apostrophe": "'",
    "bracketleft": "[",
    "bracketright": "]",
    "slash": "/",
    "backslash": "\\",
    "comma": ",",
    "period": ".",
    "grave": "`",
    "Home": "Home",
    "End": "End",
    "Prior": "Page Up",
    "Next": "Page Down",
    "Insert": "Insert",
    "Print": "Print Screen",
    "Pause": "Pause",
    "Up": "↑",
    "Down": "↓",
    "Left": "←",
    "Right": "→",
}


__MODIFIER_LOOKUP: dict[str, str] = {
    "Control_L": "Ctrl", "Control_R": "Ctrl",
    "Shift_L": "Shift", "Shift_R": "Shift",
    "Alt_L": "Alt", "Alt_R": "Alt",
    "Super_L": "Win", "Super_R": "Win",
}

__MODIFIER_ORDER: list[str] = ["Ctrl", "Alt", "Shift", "Win"]

_active_modifiers: set[str] = set()


def track_modifiers(event) -> None:
    keysym = event.keysym
    if keysym in __MODIFIER_LOOKUP:
        name = __MODIFIER_LOOKUP[keysym]
        if event.type == tk.EventType.KeyPress:
            _active_modifiers.add(name)
        elif event.type == tk.EventType.KeyRelease:
            _active_modifiers.discard(name)


def build_shortcut(event) -> list[str]:
    modifiers = [m for m in __MODIFIER_ORDER if m in _active_modifiers]

    key_name: str = SPECIAL_KEYS.get(event.keysym, event.keysym) or ""
    if len(key_name) == 1 and key_name.isalpha():
        key_name = key_name.lower()
    return modifiers + [key_name]


def on_shortcut_key(event, entry_widget, save_callback=None) -> str | None:
    keysym: str = event.keysym
    if keysym in MODIFIER_KEYS:
        return "break"

    if keysym in ("BackSpace", "Delete") and not _active_modifiers:
        entry_widget.delete(0, "end")
        if save_callback:
            save_callback([])
        return "break"

    shortcut = build_shortcut(event)

    entry_widget.delete(0, "end")
    entry_widget.insert(0, " + ".join(shortcut))

    if save_callback:
        save_callback(shortcut)
    return "break"
