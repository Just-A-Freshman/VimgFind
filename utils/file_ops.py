import ctypes
import logging
import os
import shutil
import hashlib
import subprocess
import unicodedata
import uuid
from pathlib import Path
from tkinter import Tk
from typing import Iterator

import win32clipboard
from tqdm import tqdm

from . import exclude_rules


class DROPFILES(ctypes.Structure):
    _fields_ = [
        ("pFiles", ctypes.c_uint),
        ("x", ctypes.c_long),
        ("y", ctypes.c_long),
        ("fNC", ctypes.c_int),
        ("fWide", ctypes.c_int),
    ]


def get_file_iterator(target_dir: str, exclude_rules_list: list[str] | None = None) -> Iterator[str]:
    rules_obj = exclude_rules.compile_rules(exclude_rules_list)
    stack = [target_dir]
    scanned_count = 0
    while stack:
        path = stack.pop()
        try:
            with os.scandir(path) as it:
                for entry in it:
                    scanned_count += 1
                    if scanned_count % 50 == 0:
                        print(f"正在扫描目录... 已处理 {scanned_count} 项")
                    if entry.is_dir(follow_symlinks=False):
                        rel = os.path.relpath(entry.path, target_dir).replace("\\", "/")
                        if rules_obj and rules_obj.is_excluded(rel, is_dir=True):
                            if not rules_obj.is_affected_by_negation(rel):
                                continue
                        stack.append(entry.path)
                    elif entry.is_file(follow_symlinks=False):
                        if not exclude_rules.is_accepted_extension(entry.name):
                            continue
                        if rules_obj:
                            rel = os.path.relpath(entry.path, target_dir).replace("\\", "/")
                            if rules_obj.is_excluded(rel, is_dir=False):
                                continue
                        yield entry.path
        except PermissionError:
            pass
    print(f"目录扫描完成：共处理 {scanned_count} 项")


def open_file(file_path: str | Path, highlight: bool = False) -> None:
    file_path = Path(file_path).resolve()
    if not file_path.exists():
        raise FileNotFoundError(f"文件不存在：{file_path}")

    command: list[str] = []
    if highlight:
        command = ["explorer.exe", "/select,", str(file_path)]
    else:
        command = ["explorer.exe", str(file_path)]
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False
        )
        if result.stderr:
            logging.error(f"[警告] 打开文件时产生提示：{result.stderr.strip()}")
    except subprocess.CalledProcessError as e:
        logging.error(f"打开文件失败：命令 {' '.join(command)} 执行错误，详情：{e.stderr}")
    except FileNotFoundError:
        logging.error(f"打开文件失败：未找到命令 {' '.join(command)}，请检查系统配置")
    except Exception as e:
        logging.error(f"打开文件时发生未知错误：{str(e)}")


def copy_files(*file_paths: str | Path) -> None:
    valid_paths = []
    for path in file_paths:
        abs_path = Path(path).absolute()
        if abs_path.exists() and abs_path.is_file():
            valid_paths.append(str(abs_path).replace("/", "\\") + "\0")
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


def copy_filepaths(*file_paths: str | Path, tk: Tk) -> None:
    tk.clipboard_clear()
    tk.clipboard_append("\n".join([str(i) for i in file_paths]))


def delete_file(file_path: str | Path) -> None:
    try:
        os.remove(file_path)
    except (FileNotFoundError, OSError) as e:
        logging.error(f"删除文件失败: {file_path}")


def save_as(src_path: str | Path, dest_path: str | Path, is_binary: bool = False, inplace=True) -> bool:
    src_path = Path(src_path)
    dest_path = Path(dest_path)
    if not src_path.exists() or src_path.is_dir() or dest_path.is_dir():
        return False
    try:
        dest_path = dest_path if inplace else generate_copy_name(dest_path)
        if is_binary:
            shutil.copy2(src_path, dest_path)
        else:
            with open(src_path, 'r', encoding='utf-8') as f_src, \
                 open(dest_path, 'w', encoding='utf-8') as f_dst:
                shutil.copyfileobj(f_src, f_dst)
        return True
    except (PermissionError, OSError):
        return False


def save_to_dir(*src_paths: str | Path, dest_dir: str | Path, is_binary: bool = False, inplace=True) -> bool:
    if dest_dir == "":
        return False
    dest_dir = Path(dest_dir)
    if not dest_dir.exists() or not dest_dir.is_dir():
        return False
    all_finish = True
    for src_path in src_paths:
        ans = save_as(src_path, dest_dir / Path(src_path).name, is_binary, inplace)
        if not ans:
            all_finish = False
    return all_finish


def rmtree(target_dir: str | Path) -> None:
    try:
        shutil.rmtree(target_dir)
    except Exception as e:
        logging.error(f"删除失败：{str(target_dir)}，原因：{str(e)}")


def truncate_filename(filename: str, target_width: int = 16) -> str:
    file_path = Path(filename)
    char_width = lambda x: 2 if unicodedata.east_asian_width(x) in ('F', 'W') else 1
    target_width = target_width - sum(char_width(char) for char in file_path.suffix) - 1
    curr_width = 0
    for idx, char in enumerate(file_path.stem):
        curr_width += char_width(char)
        if curr_width > target_width:
            return f"{file_path.stem[:idx]}~{file_path.suffix}"
    return str(file_path.name)


def get_metainfo(file_path: str | Path) -> int:
    return os.path.getsize(file_path)


def normalize_path(path: str) -> str:
    return os.path.normcase(os.path.realpath(path))


def generate_unique_filename(target_dir: Path, suffix: str) -> Path:
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


def generate_copy_name(file_path: str | Path) -> Path:
    orig_file_path = curr_file_path = Path(file_path)
    suffix_num = 2
    while curr_file_path.exists():
        curr_file_path = orig_file_path.with_stem(f"{orig_file_path.stem} ({suffix_num})")
        suffix_num += 1
    return curr_file_path


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


def format_bytes(value: int | float, *, as_speed: bool = False) -> str:
    suffix, pg, pm, pk, pb = ("B/s", 2, 2, 1, 1) if as_speed else ("B", 1, 0, 0, 0)
    if value >= 1024 ** 3:
        return f"{value / 1024 ** 3:.{pg}f}G{suffix}"
    if value >= 1024 ** 2:
        return f"{value / 1024 ** 2:.{pm}f}M{suffix}"
    if value >= 1024:
        return f"{value / 1024:.{pk}f}K{suffix}"
    return f"{value:.{pb}f}{suffix}"


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
