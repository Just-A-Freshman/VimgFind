from __future__ import annotations

import os
import socket
import threading

import pywintypes
import win32file



def _extract_server(unc_root: str) -> str | None:
    if not unc_root or not unc_root.startswith("\\\\"):
        return None
    parts = unc_root.split("\\")
    if len(parts) < 3:
        return None
    return parts[2]


def _is_server_reachable(unc_root: str, timeout: float = 2.0) -> bool:
    server = _extract_server(unc_root)
    if server is None:
        return False
    try:
        sock = socket.create_connection((server, 445), timeout=timeout)
        sock.close()
        return True
    except (socket.timeout, OSError, socket.gaierror):
        return False


def get_unc_root(path: str) -> str | None:
    normalized = path.replace("/", "\\")

    if normalized.startswith("\\\\?\\UNC\\"):
        normalized = "\\" + normalized[7:]
    elif normalized.startswith("\\\\?\\"):
        return None

    if not normalized.startswith("\\\\"):
        return None

    parts = normalized.split("\\")
    if len(parts) < 4:
        return None

    return "\\\\" + parts[2] + "\\" + parts[3]


def is_share_online(unc_root: str, timeout: float = 3.0) -> bool:
    if not _is_server_reachable(unc_root, timeout=min(timeout, 2.0)):
        return False

    result: bool | Exception = True

    def check() -> None:
        nonlocal result
        try:
            result = os.path.isdir(unc_root)
        except Exception as e:
            result = e

    t = threading.Thread(target=check, daemon=True)
    t.start()
    t.join(timeout=timeout)

    if t.is_alive():
        return False

    if isinstance(result, Exception):
        return False
    return result


def resolve_mapped_drive(path: str) -> str:
    if len(path) < 2 or path[1] != ":":
        return path

    drive_letter = path[:2].upper()
    try:
        drive_type = win32file.GetDriveType(drive_letter)  # type: ignore[attr-defined]
    except pywintypes.error:
        return path

    if drive_type != 4:
        return path

    try:
        info = win32file.GetUniversalName(path, win32file.REMOTE_NAME_INFO)  # type: ignore[attr-defined]
        universal_name = info[0] if info and isinstance(info, (tuple, list)) else ""
        if universal_name and universal_name.startswith("\\\\"):
            return universal_name + path[2:]
    except (pywintypes.error, IndexError, TypeError):
        pass

    return path
