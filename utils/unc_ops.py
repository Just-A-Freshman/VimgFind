from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import os
import socket

import pywintypes
import win32file


SMB_BATCH_SCANDIR_THRESHOLD = 3


def _batch_stat_via_scandir(parent: str, files: list[str]) -> dict[str, os.stat_result | None]:
    try:
        name_to_entry = {e.name: e for e in os.scandir(parent)}
    except OSError:
        return {f: None for f in files}
    result: dict[str, os.stat_result | None] = {}
    for f in files:
        entry = name_to_entry.get(os.path.basename(f))
        if entry is None:
            result[f] = None
            continue
        try:
            result[f] = entry.stat(follow_symlinks=False)
        except OSError:
            result[f] = None
    return result


def _batch_stat_via_thread(files: list[str], max_workers: int) -> dict[str, os.stat_result | None]:
    n = min(max_workers, len(files))
    if n <= 0:
        return {}
    cache: dict[str, os.stat_result | None] = {}
    with ThreadPoolExecutor(max_workers=n) as pool:
        fut_map = {pool.submit(os.stat, p): p for p in files}
        for f in as_completed(fut_map):
            p = fut_map[f]
            try:
                cache[p] = f.result()
            except OSError:
                cache[p] = None
    return cache


def _batch_exists_via_scandir(parent: str, files: list[str]) -> dict[str, bool]:
    try:
        names = {e.name for e in os.scandir(parent)}
    except OSError:
        return {}
    return {f: os.path.basename(f) in names for f in files}


def _batch_exists_via_thread(files: list[str], root_online: dict[str, bool], max_workers: int) -> dict[str, bool]:
    def exists_one(path: str, root_online: dict[str, bool]) -> bool:
        root = get_unc_root(path) if path.startswith("\\\\") else None
        if root and not root_online.get(root, True):
            return False
        try:
            return os.path.exists(path)
        except OSError:
            return False
        
    result: dict[str, bool] = {}
    n = min(max_workers, len(files))
    if n <= 0:
        return result
    with ThreadPoolExecutor(max_workers=n) as pool:
        fut_map = {pool.submit(exists_one, p, root_online): p for p in files}
        for f in as_completed(fut_map):
            result[fut_map[f]] = f.result()
    return result


def is_server_reachable(unc_root: str, timeout: float = 2.0) -> bool:
    if not unc_root or not unc_root.startswith("\\\\"):
        return False
    parts = unc_root.split("\\")
    if len(parts) < 3:
        return False
    server = parts[2]
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
    if not is_server_reachable(unc_root, timeout=min(timeout, 2.0)):
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

    groups: dict[str, list[str]] = {}
    for p in unc_paths:
        parent = os.path.dirname(p)
        groups.setdefault(parent, []).append(p)

    result: dict[str, os.stat_result | None] = {}
    for parent, files in groups.items():
        if len(files) >= SMB_BATCH_SCANDIR_THRESHOLD:
            result.update(_batch_stat_via_scandir(parent, files))
        else:
            result.update(_batch_stat_via_thread(files, max_workers))
    return result


def batch_exists(paths: list[str], timeout: float = 2.0, max_workers: int = 50) -> dict[str, bool]:
    root_online: dict[str, bool] = {}
    for p in paths:
        if p.startswith("\\\\"):
            root = get_unc_root(p)
            if root and root not in root_online:
                root_online[root] = False

    if root_online:
        n = min(max_workers, len(root_online))
        with ThreadPoolExecutor(max_workers=n) as pool:
            fut_map = {pool.submit(is_share_online, r, timeout): r for r in root_online}
            for f in as_completed(fut_map):
                root_online[fut_map[f]] = f.result()

    groups: dict[str, list[str]] = {}
    others: list[str] = []
    for p in paths:
        if not p.startswith("\\\\"):
            others.append(p)
            continue
        parent = os.path.dirname(p)
        groups.setdefault(parent, []).append(p)

    result: dict[str, bool] = {}
    for parent, files in groups.items():
        if len(files) >= SMB_BATCH_SCANDIR_THRESHOLD:
            result.update(_batch_exists_via_scandir(parent, files))
        else:
            result.update(_batch_exists_via_thread(files, root_online, max_workers))

    if others:
        result.update(_batch_exists_via_thread(others, root_online, max_workers))

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
