from pathlib import Path
from queue import Queue
from threading import Thread
from typing import Iterator, Callable, cast
from collections import namedtuple
import urllib.request
import urllib.error
import logging
import unicodedata
import os
import subprocess
import functools
import ctypes
import sys
import io
import uuid
import shutil
import json
import re

import win32clipboard
import win32con
from tkinter import Tk, messagebox, filedialog
from PIL import Image, ImageTk, ImageOps, UnidentifiedImageError
from PIL.ImageFile import ImageFile

from setting import Setting, WinInfo




class DROPFILES(ctypes.Structure):
    _fields_ = [
        ("pFiles", ctypes.c_uint),
        ("x", ctypes.c_long),
        ("y", ctypes.c_long),
        ("fNC", ctypes.c_int),
        ("fWide", ctypes.c_int),
    ]



class Decorator(object):
    progress_queue = Queue()
    @staticmethod
    def send_task(target):# -> _Wrapped[Callable[..., Any], Any, Callable[..., Any], None]:
        @functools.wraps(target)
        def inner(*args, **kwargs):
            thread = Thread(
                target=target,
                args=args,
                kwargs=kwargs,
                daemon=True
            )
            thread.start()
        return inner

    @staticmethod
    def redirect_output(target: Callable) -> Callable:
        def inner(*args, **kwargs) -> None:
            original_stdout = sys.stdout
            original_stderr = sys.stderr
            
            sys.stdout = QueueStream(Decorator.progress_queue)
            sys.stderr = QueueStream(Decorator.progress_queue)
 
            try:
                target(*args, **kwargs)
            finally:
                sys.stdout = original_stdout
                sys.stderr = original_stderr
        return inner



class FileOperation(object):
    @staticmethod
    def match_exclude_rule(folder_name: str, folder_path: str, rules: list[str]) -> bool:
        """判断一个目录是否匹配任一排除规则"""
        for rule in rules:
            rule = rule.strip()
            if not rule:
                continue
            # 规则是绝对路径 → 精确匹配（归一化后比较）
            if os.path.isabs(rule):
                if FileOperation.normalize_path(folder_path) == FileOperation.normalize_path(rule):
                    return True
            # 规则包含路径分隔符 → 路径后缀匹配
            elif '/' in rule or '\\' in rule:
                normalized_rule = FileOperation.normalize_path(rule)
                normalized_path = FileOperation.normalize_path(folder_path)
                if normalized_path.endswith(normalized_rule):
                    return True
            # 纯文件夹名 → 大小写不敏感匹配
            else:
                if folder_name.lower() == rule.lower():
                    return True
        return False

    @staticmethod
    def get_file_iterator(target_dir: str, exclude_rules: list[str] | None = None) -> Iterator[str]:
        accepted = Setting.accepted_exts
        def _scandir(path):
            try:
                with os.scandir(path) as it:
                    for entry in it:
                        if entry.is_dir(follow_symlinks=False):
                            if exclude_rules and FileOperation.match_exclude_rule(entry.name, entry.path, exclude_rules):
                                continue
                            yield from _scandir(entry.path)
                        elif entry.is_file(follow_symlinks=False):
                            name = entry.name
                            dot = name.rfind('.')
                            if dot != -1 and name[dot:].lower() in accepted:
                                yield entry.path
            except PermissionError:
                pass
        return _scandir(target_dir)

    @staticmethod
    def preview_exclusion(target_dir: str, rules: list[str]) -> list[str]:
        """扫描目录结构，返回所有被排除规则命中的文件夹路径（平铺列表）"""
        matched: list[str] = []
        try:
            with os.scandir(target_dir) as it:
                for entry in it:
                    if not entry.is_dir(follow_symlinks=False):
                        continue
                    if FileOperation.match_exclude_rule(entry.name, entry.path, rules):
                        matched.append(entry.path)
                    # 递归进入子目录
                    matched.extend(FileOperation.preview_exclusion(entry.path, rules))
        except PermissionError:
            pass
        return matched

    @staticmethod
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

    @staticmethod
    def copy_files(*file_paths: str | Path) -> None:
        valid_paths = []

        for path in file_paths:
            abs_path = Path(path).absolute()
            if abs_path.exists() and abs_path.is_file():
                valid_paths.append(str(abs_path).replace("/", "\\") + "\0")

        if not valid_paths:
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
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
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32clipboard.CF_HDROP, buffer)
        except Exception as e:
            logging.error(f"写入剪贴板失败：{e}")
        finally:
            win32clipboard.CloseClipboard()

    @staticmethod
    def copy_filepaths(*file_paths: str | Path, tk: Tk) -> None:
        tk.clipboard_clear()
        tk.clipboard_append("\n".join([str(i) for i in file_paths]))

    @staticmethod
    def delete_file(file_path: str | Path) -> None:
        try:
            os.remove(file_path)
        except (FileNotFoundError, OSError) as e:
            logging.error(f"删除文件失败: {file_path}")

    @staticmethod
    def save_as(src_path: str | Path, dest_path: str | Path, is_binary: bool = False, inplace=True) -> bool:
        src_path = Path(src_path)
        dest_path = Path(dest_path)
        if not src_path.exists() or src_path.is_dir() or dest_path.is_dir():
            return False
        read_mode = 'rb' if is_binary else 'r',
        write_mode = 'wb' if is_binary else 'w'
        encoding = None if is_binary else 'utf-8'
        try:
            with open(src_path, mode=read_mode[0], encoding=encoding) as f_src:
                content = f_src.read()
            dest_path = dest_path if inplace else FileOperation.generate_copy_name(dest_path)
            with open(dest_path, mode=write_mode, encoding=encoding) as f_dst:
                f_dst.write(content)
            return True
        except (PermissionError, OSError):
            return False

    @staticmethod
    def save_to_dir(*src_paths: str | Path, dest_dir: str | Path, is_binary: bool = False, inplace=True) -> bool:
        if dest_dir == "":
            return False
        dest_dir = Path(dest_dir)
        if not dest_dir.exists() or not dest_dir.is_dir():
            return False
        all_finish = True
        for src_path in src_paths:
            ans = FileOperation.save_as(src_path, dest_dir / Path(src_path).name, is_binary, inplace)
            if not ans:
                all_finish = False
        return all_finish

    @staticmethod
    def clear_folder_all(target_dir: str | Path) -> None:
        target_dir = Path(target_dir)
        if not target_dir.exists() or not target_dir.is_dir():
            return
        
        for item_path in target_dir.glob("*"):
            try:
                if item_path.is_file() or item_path.is_symlink():
                    os.remove(item_path)
                elif item_path.is_dir():
                    shutil.rmtree(item_path)
            except PermissionError:
                logging.error(f"权限不足，无法删除：{item_path}")
            except FileNotFoundError:
                return
            except Exception as e:
                logging.error(f"删除失败 {item_path}：{str(e)}")

    @staticmethod
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

    @staticmethod
    def get_metainfo(file_path: str | Path) -> int:
        file_size = os.path.getsize(file_path)
        return file_size

    @staticmethod
    def normalize_path(path: str) -> str:
        return os.path.normcase(os.path.realpath(path))

    @staticmethod
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

    @staticmethod
    def generate_copy_name(file_path: str | Path) -> Path:
        orig_file_path = curr_file_path = Path(file_path)
        suffix_num = 2
        while curr_file_path.exists():
            curr_file_path = orig_file_path.with_stem(f"{orig_file_path.stem} ({suffix_num})")
            suffix_num += 1
        return curr_file_path
    
    @staticmethod
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



class ImageOperation(object):
    @staticmethod
    def parse_image_from_clipboard_bytes() -> None | ImageFile:
        try:
            win32clipboard.OpenClipboard()
            if not win32clipboard.IsClipboardFormatAvailable(win32con.CF_DIB):
                return None
            dib_data = win32clipboard.GetClipboardData(win32con.CF_DIB)
            return Image.open(io.BytesIO(dib_data))
        except Exception as e:
            return None
        finally:
            win32clipboard.CloseClipboard()

    @staticmethod
    def parse_image_from_path(image_path: str | Path) -> ImageFile | None:
        try:
            return Image.open(image_path)
        except (UnidentifiedImageError, OSError, FileNotFoundError) as e:
            return
        
    @staticmethod
    def parse_image_from_url(url: str) -> Image.Image | None:
        url_lower = url.lower()
        is_likely_image = any(url_lower.endswith(ext) for ext in Setting.accepted_exts)
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as response:
                content_type = response.headers.get('Content-Type', '').lower()
                is_image_by_content = content_type.startswith('image/')
                if not is_image_by_content and not is_likely_image:
                    raise ValueError(f"URL不是图像链接: Content-Type={content_type}, URL={url}")
                image_data = response.read()
                
                image: Image.Image = Image.open(io.BytesIO(image_data)).convert("RGB")
                if hasattr(image, 'load'):
                    image.load()
                return image
        except Exception:
            return

    @staticmethod
    def save_as_image(src_path: Path) -> None:
        filetypes = [
            ("PNG 图片", "*.png"),
            ("JPEG 图片", "*.jpg"),
            ("WebP 图片", "*.webp"),
            ("BMP 图片", "*.bmp"),
            ("GIF 图片", "*.gif"),
            ("TIFF 图片", "*.tiff"),
        ]
        dest = filedialog.asksaveasfilename(
            defaultextension=src_path.suffix,
            filetypes=filetypes,
            initialfile=src_path.stem
        )
        if not dest:
            return
        dest = Path(dest)
        try:
            if dest.suffix.lower() == src_path.suffix.lower():
                if not FileOperation.save_as(src_path, dest, True):
                    raise Exception("系统权限错误！")
            img: Image.Image = Image.open(src_path)
            if dest.suffix.lower() in ('.jpg', '.jpeg') and img.mode == 'RGBA':
                img = img.convert('RGB')
            img.save(dest)
            return 
        except Exception as e:
            messagebox.showerror("保存失败", str(e))
            return
        
    

LoaderResult = namedtuple("LoaderResult", ["item", "size", "photo", "error"])
class ImageLoader:
    def __init__(self) -> None:
        self.task_queue: Queue[tuple] = Queue()
        self.result_queue: Queue[LoaderResult] = Queue()
        self.threads: list[Thread] = []
        self.running = True
        for _ in range(10):
            thread = Thread(target=self._worker, daemon=True)
            thread.start()
            self.threads.append(thread)
    
    def add_task(self, item: str, image_path: str, thumbnail_size: int) -> None:
        self.task_queue.put((item, image_path, thumbnail_size))
    
    def _worker(self) -> None:
        while self.running:
            try:
                item, image_path, thumbnail_size = self.task_queue.get(timeout=1)
            except Exception:
                continue
            img = ImageOperation.parse_image_from_path(image_path)
            if img is None:
                self.result_queue.put(LoaderResult(
                    item=item, size=(0, 0), photo=None, error="加载图片失败！"
            ))
            else:
                width, height = img.size
                img.thumbnail((thumbnail_size, thumbnail_size))
                img =  ImageOps.exif_transpose(img)
                self.result_queue.put(LoaderResult(
                    item=item,
                    size=(width, height), 
                    photo=ImageTk.PhotoImage(img), 
                    error=""
                ))
            self.task_queue.task_done()
                
    def get_results(self) -> list[LoaderResult]:
        results = []
        while not self.result_queue.empty():
            results.append(self.result_queue.get_nowait())
        return results
    
    def stop(self) -> None:
        self.running = False
        for thread in self.threads:
            thread.join(timeout=1)



class QueueStream:
    def __init__(self, queue: Queue) -> None:
        self.queue = queue

    def write(self, message: str) -> None:
        clean_message = message.replace('\r', '').replace('\n', '').strip()
        if clean_message:
            self.queue.put(clean_message)

    def flush(self) -> None:
        pass



UpdateCheckResult = namedtuple(
    "UpdateCheckResult",
    ["has_update", "latest_version", "release_url", "download_url", "release_body", "current_version", "error"]
)
class UpdateChecker:
    """
    Asset 命名规范:
      完整包:   VimgFind-{version}-{platform}.{ext}
      增量更新: VimgFind-{version}-{platform}-update.{ext}

    Platform 标签:
      win64     → Windows 64-bit
      macos     → macOS (Universal)
      linux-x64 → Linux x86_64
    """

    API_URL = "https://api.github.com/repos/Just-A-Freshman/VimgFind/releases/latest"
    _VERSION_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")

    @staticmethod
    def _detect_platform_tag() -> str:
        system = sys.platform
        if system == 'win32':
            return 'win64'
        elif system == 'darwin':
            return 'macos'
        elif system.startswith('linux'):
            return 'linux-x64'
        return 'unknown'

    @staticmethod
    def _parse_version(text: str) -> tuple[int, int, int] | None:
        m = UpdateChecker._VERSION_RE.search(text)
        if m:
            return cast(tuple[int, int, int], tuple(int(g) for g in m.groups()))
        return None

    @staticmethod
    def _find_latest_asset_version(assets: list[dict]) -> tuple[int, int, int] | None:
        best: tuple[int, int, int] | None = None
        for asset in assets:
            v = UpdateChecker._parse_version(asset["name"])
            if v and (best is None or v > best):
                best = v
        return best

    @staticmethod
    def _match_download_url(assets: list[dict], version: str) -> str | None:
        platform_tag = UpdateChecker._detect_platform_tag()
        for asset in assets:
            if re.match(f"VimgFind-{version}-{platform_tag}-update", asset["name"]):
                return asset["browser_download_url"]

        return None

    @staticmethod
    def check(timeout: int = 5) -> UpdateCheckResult:
        try:
            req = urllib.request.Request(
                UpdateChecker.API_URL,
                headers={
                    "User-Agent": f"VimgFind/{WinInfo.version}",
                    "Accept": "application/vnd.github.v3+json",
                },
            )
            with urllib.request.urlopen(req, timeout=timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return UpdateCheckResult(
                False, "", "", "", "", WinInfo.version, f"HTTP {e.code}: {e.reason}"
            )
        except (urllib.error.URLError, OSError) as e:
            return UpdateCheckResult(
                False, "", "", "", "", WinInfo.version, f"网络错误: {e}"
            )
        except (json.JSONDecodeError, ValueError) as e:
            return UpdateCheckResult(
                False, "", "", "", "", WinInfo.version, f"响应解析失败: {e}"
            )

        release_url = data.get("html_url", WinInfo.repo_url)
        release_body = (data.get("body") or "").strip()
        assets = data.get("assets", [])

        latest_tuple = UpdateChecker._find_latest_asset_version(assets)
        if latest_tuple is None:
            return UpdateCheckResult(
                False, "", "", "", "", WinInfo.version, "无法识别远程版本号"
            )

        latest_version = ".".join(str(g) for g in latest_tuple)
        current_tuple = UpdateChecker._parse_version(WinInfo.version)
        has_update = current_tuple is not None and latest_tuple > current_tuple

        download_url = UpdateChecker._match_download_url(assets, latest_version)

        return UpdateCheckResult(
            has_update, latest_version, release_url,
            download_url or release_url, release_body, WinInfo.version, None
        )


