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


def parse_event_to_shortcut(event) -> list[str]:
    modifiers: list[str] = []
    if event.state & 0x0004:
        modifiers.append("Ctrl")
    if event.state & 0x0001:
        modifiers.append("Shift")
    if event.state & 0x0008:
        modifiers.append("Alt")
    if event.state & 0x0040:
        modifiers.append("Win")

    key_name: str = SPECIAL_KEYS.get(event.keysym, event.keysym) or ""
    if len(key_name) == 1 and key_name.isalpha():
        key_name = key_name.lower()

    return modifiers + [key_name]
