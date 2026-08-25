from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import os
import socket

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


def safe_exists(path: str | os.PathLike, timeout: float = 2.0) -> bool:
    path_str = str(path)
    unc_root = get_unc_root(path_str)
    if unc_root is not None:
        if not is_share_online(unc_root, timeout=timeout):
            return False
    return os.path.exists(path_str)


def batch_stat(paths: list[str], max_workers: int = 50) -> dict[str, os.stat_result | None]:
    unc_paths = [p for p in paths if p.startswith("\\\\")]
    if not unc_paths:
        return {}

    n = min(max_workers, len(unc_paths))
    cache: dict[str, os.stat_result | None] = {}
    with ThreadPoolExecutor(max_workers=n) as pool:
        fut_map = {pool.submit(os.stat, p): p for p in unc_paths}
        for f in as_completed(fut_map):
            p = fut_map[f]
            try:
                cache[p] = f.result()
            except OSError:
                cache[p] = None
    return cache


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
