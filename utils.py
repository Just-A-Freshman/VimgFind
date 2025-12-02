from pathlib import Path
from queue import Queue
from threading import Thread
from typing import Iterator
import os
import subprocess
import platform
import functools
import sys


from setting import Setting




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
    def redirect_output(target):
        def inner(*args, **kwargs):
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
        for file_path in Path(target_dir).rglob('*'):
            if file_path.is_file() and file_path.suffix.lower() in Setting.accepted_exts:
                yield str(file_path)

    @staticmethod
    def open_file(file_path: str | Path, highlight: bool = False) -> None:
        file_path = Path(file_path).resolve()
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在：{file_path}")

        system = platform.system()
        command: list[str] = []

        try:
            if system == "Windows":
                if highlight:
                    command = ["explorer.exe", "/select,", str(file_path)]
                else:
                    command = ["explorer.exe", str(file_path)]
            elif system == "Darwin":  # macOS
                if highlight:
                    command = ["open", "-R", str(file_path)]
                else:
                    command = ["open", str(file_path)]
            elif system == "Linux":
                # 不支持高亮
                command = ["xdg-open", str(file_path)]
            else:
                raise OSError(f"暂不支持的操作系统：{system}")

            result = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            if result.stderr:
                print(f"[警告] 打开文件时产生提示：{result.stderr.strip()}")

        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"打开文件失败：命令 {' '.join(command)} 执行错误，详情：{e.stderr}") from e
        except FileNotFoundError:
            raise RuntimeError(f"打开文件失败：未找到命令 {' '.join(command)}，请检查系统配置") from None
        except Exception as e:
            raise RuntimeError(f"打开文件时发生未知错误：{str(e)}") from e

    @staticmethod
    def copy_file(file_path: str | Path) -> None:
        # 注意，这个复制方式仅限Windows平台
        if not Path(file_path).exists():
            return
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        args = ['powershell', f'Get-Item {file_path} | Set-Clipboard']
        subprocess.Popen(args=args, startupinfo=startupinfo)

    @staticmethod
    def delete_file(file_path: str | Path) -> None:
        try:
            os.remove(file_path)
        except (FileNotFoundError, OSError) as e:
            print(e)

    @staticmethod
    def get_metainfo(file_path: str | Path) -> int:
        file_size = os.path.getsize(file_path)
        return file_size



class QueueStream:
    def __init__(self, queue: Queue) -> None:
        self.queue = queue

    def write(self, message) -> None:
        clean_message = message.replace('\r', '').replace('\n', '').strip()
        if clean_message:
            self.queue.put(clean_message)

    def flush(self) -> None:
        pass


