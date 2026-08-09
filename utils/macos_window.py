from __future__ import annotations

from AppKit import NSApp # type: ignore


def windows() -> list:
    return list(NSApp.windows())


def enable_frame_autosave(window_title: str, name: str) -> None:
    for w in windows():
        if w.title() == window_title:
            try:
                w.setFrameAutosaveName_(name)
            except Exception:
                pass
            return


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
