from __future__ import annotations

from pathlib import Path
from tkinter import Tk
from typing import Callable, Iterator, Literal
from functools import lru_cache
import ctypes
import hashlib
import logging
import os
import queue
import shutil
import subprocess
import threading

from .i18n import _
from . import decorators
from . import exclude_rules
from . import unc_ops as unc_ops


class DROPFILES(ctypes.Structure):
    _fields_ = [
        ("pFiles", ctypes.c_uint),
        ("x", ctypes.c_long),
        ("y", ctypes.c_long),
        ("fNC", ctypes.c_int),
        ("fWide", ctypes.c_int),
    ]


def get_file_iterator(
    target_dir: str,
    exclude_rules_list: list[str] | None = None,
    max_workers: int = 8,
    stop_check: Callable[[], bool] | None = None,
) -> Iterator[str]:
    rules_obj = exclude_rules.compile_rules(exclude_rules_list)
    dir_queue: queue.Queue[str | None] = queue.Queue()
    result_queue: queue.Queue[str | None] = queue.Queue()
    scanned_count = 0
    count_lock = threading.Lock()

    pending = [0]  # 待处理目录数（队列中 + 正在处理）
    pending_lock = threading.Lock()
    all_done = threading.Event()
    stop_event = threading.Event()

    def add_dir(dir_path: str) -> None:
        with pending_lock:
            pending[0] += 1
        dir_queue.put(dir_path)

    def worker() -> None:
        nonlocal scanned_count
        while True:
            dir_path = dir_queue.get()
            if dir_path is None:
                break
            try:
                with os.scandir(dir_path) as it:
                    for entry in it:
                        if stop_event.is_set():
                            return
                        if stop_check and stop_check():
                            stop_event.set()
                            return
                        with count_lock:
                            scanned_count += 1
                            if scanned_count % 50 == 0:
                                print(_("正在扫描目录... 已处理 {scanned_count} 项", scanned_count=scanned_count))
                        if entry.is_dir(follow_symlinks=False):
                            if rules_obj and rules_obj.should_skip_dir(entry, target_dir):
                                continue
                            add_dir(entry.path)
                        elif entry.is_file(follow_symlinks=False):
                            if rules_obj and rules_obj.should_skip_file(entry, target_dir):
                                continue
                            result_queue.put(entry.path)
            except PermissionError as e:
                logging.warning(f"访问权限不足: {dir_path} ({e})")
            except OSError as e:
                logging.warning(f"跳过不可访问的目录: {dir_path} ({e})")
            finally:
                with pending_lock:
                    pending[0] -= 1
                    if pending[0] == 0:
                        all_done.set()

    add_dir(target_dir)
    threads = [threading.Thread(target=worker, daemon=True) for _ in range(max_workers)]
    for t in threads:
        t.start()

    def watcher() -> None:
        all_done.wait()
        for _ in threads:
            dir_queue.put(None)
        result_queue.put(None)

    threading.Thread(target=watcher, daemon=True).start()

    try:
        while True:
            if stop_event.is_set():
                break
            if stop_check and stop_check():
                stop_event.set()
                break
            try:
                item = result_queue.get(timeout=0.3)
            except queue.Empty:
                continue
            if item is None:
                break
            yield item
    finally:
        stop_event.set()
        all_done.set()  # 解阻塞 watcher，让它发结束信号
        print(_("目录扫描完成：共处理 {scanned_count} 项", scanned_count=scanned_count))


@decorators.send_task
def open_file(file_path: str | Path, highlight: bool = False) -> None:
    command: list[str] = []
    if highlight:
        command = ["explorer.exe", "/select,", str(file_path)]
    else:
        command = ["explorer.exe", str(file_path)]
    returncode, _, stderr = run_cmd(command)
    if returncode == -1:
        logging.error(f"打开文件失败：命令 {' '.join(command)} 执行错误，详情：{stderr}")


def copy_files(*file_paths: str | Path) -> None:
    import win32clipboard
    paths = [str(Path(p).absolute()) for p in file_paths]
    exists_map = unc_ops.batch_exists(paths)
    valid_paths = [p.replace("/", "\\") + "\0" for p in paths if exists_map.get(p, False)]
    if not valid_paths:
        try:
            win32clipboard.OpenClipboard()
        except Exception:
            return
        try:
            win32clipboard.EmptyClipboard()
        except Exception:
            pass
        finally:
            win32clipboard.CloseClipboard()
        return

    paths_str = "".join(valid_paths) + "\0"
    paths_wchar = paths_str.encode("utf-16le")
    df = DROPFILES()
    df.pFiles = ctypes.sizeof(DROPFILES)
    df.fWide = 1
    buffer = ctypes.string_at(ctypes.pointer(df), ctypes.sizeof(df)) + paths_wchar
    try:
        win32clipboard.OpenClipboard()
    except Exception as e:
        logging.error(f"打开剪贴板失败：{e}")
        return
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_HDROP, buffer)
    except Exception as e:
        logging.error(f"写入剪贴板失败：{e}")
    finally:
        win32clipboard.CloseClipboard()


def copy_text(*text: str, tk: Tk) -> None:
    tk.clipboard_clear()
    tk.clipboard_append("\n".join([str(i) for i in text]))


def delete_file(file_path: str | Path, hard=True) -> None:
    try:
        from send2trash import send2trash
        os.remove(file_path) if hard else send2trash(file_path)
    except (FileNotFoundError, OSError) as e:
        logging.error(f"删除文件失败: {file_path}")


def save_as(src_path: str | Path, dest_path: str | Path) -> bool:
    src_path = Path(src_path)
    dest_path = Path(dest_path)
    if not unc_ops.safe_exists(src_path) or src_path.is_dir() or dest_path.is_dir():
        return False
    try:
        shutil.copy2(src_path, dest_path)
        return True
    except (PermissionError, OSError):
        return False


def rmtree(target_dir: str | Path) -> None:
    try:
        shutil.rmtree(target_dir)
    except Exception as e:
        logging.error(f"删除失败：{str(target_dir)}，原因：{str(e)}")


def run_cmd(cmd: str | list[str], cwd: str | None = None) -> tuple[int, str, str]:
    try:
        result = subprocess.run(
            cmd, shell=isinstance(cmd, str), text=True,
            capture_output=True, cwd=cwd, stdin=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        return result.returncode, result.stdout, result.stderr
    except FileNotFoundError as e:
        return -1, "", str(e)
    except Exception as e:
        return -1, "", str(e)


def truncate_filename(filename: str, target_width: int = 16) -> str:
    import unicodedata
    file_path = Path(filename)
    char_width = lambda x: 2 if unicodedata.east_asian_width(x) in ('F', 'W') else 1
    target_width = target_width - sum(char_width(char) for char in file_path.suffix) - 1
    curr_width = 0
    for idx, char in enumerate(file_path.stem):
        curr_width += char_width(char)
        if curr_width > target_width:
            return f"{file_path.stem[:idx]}~{file_path.suffix}"
    return str(file_path.name)


def get_path_type(path: str) -> Literal["local", "unc_ip", "unc_hostname", "mapped_drive"]:
    normalized = path.replace("/", "\\").rstrip("\\")
    
    if normalized.startswith("\\\\"):
        if normalized.startswith("\\\\?\\UNC\\"):
            normalized = "\\" + normalized[7:]
        elif normalized.startswith("\\\\?\\"):
            return "local"

        parts = normalized.split("\\")
        if len(parts) >= 3:
            server = parts[2]
            if server and all(p.isdigit() for p in server.split(".")):
                return "unc_ip"
            return "unc_hostname"
        return "local"

    if len(normalized) >= 2 and normalized[1] == ":":
        try:
            import win32file
            import pywintypes
        except ImportError:
            pass
        else:
            try:
                drive_letter = normalized[:2].upper()
                drive_type = win32file.GetDriveType(drive_letter)
                if drive_type == 4:
                    return "mapped_drive"
            except pywintypes.error:
                pass

    return "local"


def get_metainfo(file_path: str | Path) -> int:
    return os.path.getsize(file_path)


def display_normalize(path: str | Path) -> str:
    if get_path_type(str(path)) == "local":
        return str(path.resolve()) if isinstance(path, Path) else str(Path(path).resolve())
    return fast_normalize(path)


def fast_normalize(path: str | Path) -> str:
    s = os.fspath(path)
    if not os.path.isabs(s):
        s = os.path.abspath(s)
    return os.path.normcase(os.path.normpath(s))


@lru_cache
def real_normalize(path: str | Path) -> str:
    return os.path.normcase(os.path.realpath(path))


def is_path_under(path: str | Path, parent_dir: str | Path) -> bool:
    fast_path = fast_normalize(path)
    fast_parent = fast_normalize(parent_dir)
    if fast_path.startswith(fast_parent.rstrip(os.sep) + os.sep):
        return True
    if fast_path[:2] != fast_parent[:2]:
        return False
    if fast_path.startswith("\\\\") and fast_parent.startswith("\\\\"):
        pp = fast_path.split("\\")
        qp = fast_parent.split("\\")
        if len(pp) < 4 or len(qp) < 4 or pp[2] != qp[2] or pp[3] != qp[3]:
            return False
        return False
    real_path = real_normalize(fast_path)
    real_parent = real_normalize(fast_parent)
    return real_path.startswith(real_parent.rstrip(os.sep) + os.sep)


def generate_unique_filename(target_dir: Path, suffix: str) -> Path:
    import uuid
    random_name = uuid.uuid4().hex
    if suffix and not suffix.startswith("."):
        suffix = f".{suffix}"
    filename = f"{random_name}{suffix}"
    full_path = target_dir / filename
    max_attempts = 10
    attempts = 0
    while full_path.exists() and attempts < max_attempts:
        random_name = uuid.uuid4().hex
        filename = f"{random_name}{suffix}"
        full_path = target_dir / filename
        attempts += 1
    if attempts >= max_attempts:
        raise RuntimeError("超出最大尝试次数，无法生成唯一文件名")
    return full_path


def extract_file_paths(text: str) -> list[str]:
    paths = []
    i = 0
    n = len(text)
    while i < n:
        while i < n and text[i].isspace():
            i += 1
        if i >= n:
            break
        if text[i] == '{':
            brace_count = 1
            j = i + 1
            while j < n and brace_count > 0:
                if text[j] == '{':
                    brace_count += 1
                elif text[j] == '}':
                    brace_count -= 1
                j += 1
            if brace_count == 0:
                path = text[i+1:j-1]
                paths.append(path.strip())
                i = j
            else:
                j = i + 1
                while j < n and not text[j].isspace():
                    j += 1
                path = text[i:j].strip()
                if path:
                    paths.append(path)
                i = j
        else:
            j = i
            while j < n and not text[j].isspace():
                j += 1
            path = text[i:j].strip()
            if path:
                paths.append(path)
            i = j
    return paths


def get_folder_size(folder_path: str | Path) -> int:
    total_size = 0
    try:
        with os.scandir(folder_path) as entries:
            for entry in entries:
                if entry.is_file(follow_symlinks=False):
                    total_size += entry.stat(follow_symlinks=False).st_size
                elif entry.is_dir(follow_symlinks=False):
                    total_size += get_folder_size(entry.path)
    except (PermissionError, OSError):
        pass
    return total_size


def format_bytes(
        value: int | float,
        unit: Literal["B", "KB", "MB", "GB", "auto"] = "auto",
        decimal_parts: dict[str, int] = {}
    ) -> str:
    if unit == "GB" or (unit == "auto" and value >= 1024 ** 3):
        return "{:.{}f}GB".format(value / 1024 ** 3, decimal_parts.get('GB', 1))

    if unit == "MB" or (unit == "auto" and value >= 1024 ** 2):
        return "{:.{}f}MB".format(value / 1024 ** 2, decimal_parts.get('MB', 1))

    if unit == "KB" or (unit == "auto" and value >= 1024):
        return "{:.{}f}KB".format(value / 1024, decimal_parts.get('KB', 0))

    return "{:.{}f}B".format(value, decimal_parts.get('B', 0))


def merge_dirs(src: Path, dst: Path, skip_names: set[str] | None = None) -> None:
    if skip_names is None:
        skip_names = set()
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        if item.name in skip_names:
            continue
        target = dst / item.name
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            merge_dirs(item, target, skip_names)
        else:
            item.replace(target)


def verify_file_sha256(file_path: Path | str, expected: str) -> bool:
    try:
        algo, expected_hash = expected.split(":", 1)
    except ValueError:
        return False
    if algo != "sha256":
        return False
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while True:
            data = f.read(8192)
            if not data:
                break
            sha256.update(data)
    return sha256.hexdigest() == expected_hash.lower()
