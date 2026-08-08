from __future__ import annotations

from pathlib import Path
from tkinter import Tk
from typing import Iterator, Literal
import hashlib
import logging
import os
import shutil
import subprocess
import unicodedata
import urllib.parse
import uuid
import time

from send2trash import send2trash
from AppKit import NSPasteboard
from Foundation import NSURL

from .i18n import _
from . import exclude_rules


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
                        print(_("正在扫描目录... 已处理 {scanned_count} 项", scanned_count=scanned_count))
                    if entry.is_dir(follow_symlinks=False):
                        if rules_obj and rules_obj.should_skip_dir(entry, target_dir):
                            continue
                        stack.append(entry.path)
                    elif entry.is_file(follow_symlinks=False):
                        if rules_obj and rules_obj.should_skip_file(entry, target_dir):
                            continue
                        yield entry.path
        except PermissionError:
            pass
    print(_("目录扫描完成：共处理 {scanned_count} 项", scanned_count=scanned_count))


def open_file(file_path: str | Path, highlight: bool = False) -> None:
    file_path = Path(file_path).resolve()
    if not file_path.exists():
        logging.error(f"文件不存在：{file_path}，无法打开！")

    command: list[str] = []
    if highlight:
        command = ["open", "-R", str(file_path)]
    else:
        command = ["open", str(file_path)]
    returncode, _, stderr = run_cmd(command)
    if returncode == -1:
        logging.error(f"打开文件失败：命令 {' '.join(command)} 执行错误，详情：{stderr}")


def copy_files(*file_paths: str | Path) -> None:
    valid_paths = []
    for path in file_paths:
        abs_path = Path(path).absolute()
        if abs_path.exists() and abs_path.is_file():
            valid_paths.append(abs_path)
    pb = NSPasteboard.generalPasteboard()
    pb.clearContents()
    if not valid_paths:
        return
    urls = [NSURL.fileURLWithPath_(str(p)) for p in valid_paths]
    if not pb.writeObjects_(urls):
        logging.error("写入剪贴板失败：无法写入文件 URL")


def copy_text(*text: str, tk: Tk) -> None:
    tk.clipboard_clear()
    tk.clipboard_append("\n".join([str(i) for i in text]))


def delete_file(file_path: str | Path, hard=True) -> None:
    try:
        os.remove(file_path) if hard else send2trash(file_path)
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


def normalize_path(path: str | Path) -> str:
    return os.path.normcase(os.path.realpath(path))


def is_path_under(path: str, parent_dir: str, *, normalized: bool = False) -> bool:
    if not normalized:
        path = normalize_path(path)
        parent_dir = normalize_path(parent_dir)
    parent_with_sep = parent_dir.rstrip(os.sep) + os.sep
    return path.startswith(parent_with_sep)


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
    orig = file_path if isinstance(file_path, Path) else Path(file_path)
    if not orig.exists():
        return orig
    
    stem = orig.stem
    candidate = orig.with_stem(f"{stem}(2)")
    if not candidate.exists():
        return candidate
    low, high = 2, 4
    while True:
        candidate = orig.with_stem(f"{stem}({high})")
        if not candidate.exists():
            break
        low = high
        high *= 2
        if high > 1024:
            ts = int(time.time() * 1000)
            return orig.with_stem(f"{stem}_{ts}")

    while low + 1 < high:
        mid = (low + high) // 2
        candidate = orig.with_stem(f"{stem}({mid})")
        if candidate.exists():
            low = mid
        else:
            high = mid

    return orig.with_stem(f"{stem}({high})")


def url_to_path(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("file://"):
        parsed = urllib.parse.urlparse(raw)
        return urllib.parse.unquote(parsed.path)
    return raw


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
                paths.append(url_to_path(path))
                i = j
            else:
                j = i + 1
                while j < n and not text[j].isspace():
                    j += 1
                path = text[i:j].strip()
                if path:
                    paths.append(url_to_path(path))
                i = j
        else:
            j = i
            while j < n and not text[j].isspace():
                j += 1
            path = text[i:j].strip()
            if path:
                paths.append(url_to_path(path))
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
