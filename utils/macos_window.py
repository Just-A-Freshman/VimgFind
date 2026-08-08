from __future__ import annotations

from AppKit import NSApp, NSScreen # type: ignore



_WINDOW_WIDTH_RATIO = 1660 / 2880
_WINDOW_HEIGHT_RATIO = 1120 / 1400


def fit_window_size(width: int, height: int) -> tuple[int, int]:
    frame = NSScreen.mainScreen().frame()
    sw, sh = int(frame.size.width), int(frame.size.height)
    scale = min(sw * _WINDOW_WIDTH_RATIO / width, sh * _WINDOW_HEIGHT_RATIO / height)
    scale = max(scale, 1.0)
    return round(width * scale), round(height * scale)


def windows() -> list:
    return list(NSApp.windows())


def max_level() -> int:
    return max((w.level() for w in windows()), default=0)


def raise_above_others(target_titles: set[str]) -> bool:
    others_levels = [w.level() for w in windows() if w.title() not in target_titles]
    base = max(others_levels, default=0)
    raised = False
    for w in windows():
        if w.title() in target_titles:
            try:
                w.setLevel_(base + 1)
                raised = True
            except Exception:
                pass
    return raised


def raise_new_windows(before: set) -> None:
    new_windows = set(windows()) - before
    if not new_windows:
        return
    base = max_level()
    for w in new_windows:
        try:
            w.setLevel_(base + 1)
        except Exception:
            pass
