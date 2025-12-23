from pathlib import Path
from queue import Queue
from threading import Thread
from typing import Iterator
import os
import subprocess
import functools
import ctypes
import sys
import io
import uuid
import shutil
import logging


import win32clipboard
import win32con
from PIL import Image, UnidentifiedImageError
from PIL.ImageFile import ImageFile
from tqdm import tqdm


from setting import Setting




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
    def redirect_output(target):# -> Callable[..., None]:
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
                Decorator.progress_queue.put("当前索引的图库")
        return inner



class FileOperation(object):
    @staticmethod
    def get_file_iterator(target_dir) -> Iterator[str]:
        for file_path in tqdm(Path(target_dir).rglob('*'), desc="扫描文件"):
            if file_path.is_file() and file_path.suffix.lower() in Setting.accepted_exts:
                yield str(file_path)

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
    def delete_file(file_path: str | Path) -> None:
        try:
            os.remove(file_path)
        except (FileNotFoundError, OSError) as e:
            logging.error(f"删除文件失败: {file_path}")

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
    def get_metainfo(file_path: str | Path) -> int:
        file_size = os.path.getsize(file_path)
        return file_size

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



class ImageOperation(object):
    @staticmethod
    def get_clipboard_image_bytes() -> None | ImageFile:
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
    def get_image_obj(image_path: str | Path) -> ImageFile | None:
        try:
            return Image.open(image_path)
        except (UnidentifiedImageError, OSError, FileNotFoundError) as e:
            return
        

class QueueStream:
    def __init__(self, queue: Queue) -> None:
        self.queue = queue

    def write(self, message: str) -> None:
        clean_message = message.replace('\r', '').replace('\n', '').strip()
        if clean_message:
            self.queue.put(clean_message)

    def flush(self) -> None:
        pass


