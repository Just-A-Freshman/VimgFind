
from pathlib import Path
from queue import Queue
from threading import Thread
import os
import json
import subprocess
import platform
import functools
import sys

from core import EfficientIR

from tqdm import tqdm


NOTEXISTS = 'NOTEXISTS'


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
    def get_file_list(target_dir) -> list[str]:
        accepted_exts = ['.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.gif', '.webp']
        file_path_list = []
        for root, dirs, files in os.walk(target_dir):
            for name in files:
                if name.lower().endswith(tuple(accepted_exts)):
                    file_path_list.append(os.path.join(root, name))
        return file_path_list

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
    def get_metainfo(file_path) -> int:
        file_size = os.path.getsize(file_path)
        return file_size



class Utils:
    def __init__(self, config) -> None:
        self.__max_match_count: int = config["max_match_count"]
        self.__name_index_path: Path = Path(config['name_index_path'])
        self.ir_engine = EfficientIR(
            config['img_size'],
            config['index_capacity'],
            config['index_path'],
            config['model_path'],
        )

    def _get_name_index(self) -> list[list]:
        if not self.__name_index_path.exists():
            Path.mkdir(self.__name_index_path.parent, exist_ok=True)
            self._save_name_index([])
            return []
        try:
            with open(self.__name_index_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"警告：{self.__name_index_path} 文件损坏，将使用空索引")
            self._save_name_index([])
            return []
        except Exception as e:
            print(f"读取索引文件失败：{e}，将使用空索引")
            self._save_name_index([])
            return []

    def _save_name_index(self, name_index: list) -> None:
        with open(self.__name_index_path, 'w', encoding='utf-8') as wp:
            json.dump(name_index, wp, ensure_ascii=False, indent=4)

    @property
    def max_match_count(self) -> int:
        valid_index_count = 0
        name_index = self._get_name_index()
        for _, metainfo in name_index:
            if metainfo != NOTEXISTS:
                valid_index_count += 1
            if valid_index_count > self.__max_match_count:
                return self.__max_match_count
        return valid_index_count

    def _get_changed_files_index(self, name_index) -> list[tuple[int, str]]:
        changed_files_index = []
        for idx, [index_file, old_metainfo] in enumerate(name_index):
            if old_metainfo == NOTEXISTS:
                continue
            new_metainfo = FileOperation.get_metainfo(index_file)
            if old_metainfo != new_metainfo:
                name_index[idx][1] = new_metainfo
                changed_files_index.append((idx, index_file))
        return changed_files_index
    
    def _get_new_files_index(self, name_index: list, target_dir: str) -> list[tuple[int, str]]:
        new_files_index = []

        current_files = FileOperation.get_file_list(target_dir)
        existing_files = set(i[0] for i in name_index)
        new_files = [f for f in current_files if f not in existing_files]

        if not new_files:
            return []

        for idx, [_, old_metainfo] in enumerate(name_index):
            new_file = new_files[-1]
            new_metainfo = FileOperation.get_metainfo(new_file)
            if old_metainfo == NOTEXISTS:
                name_index[idx] = [new_file, new_metainfo]
                new_files_index.append((idx, new_file))
                new_files.pop()
            if len(new_files) == 0:
                break
        for new_file in new_files:
            metainfo = FileOperation.get_metainfo(new_file)
            name_index.append([new_file, metainfo])
            new_files_index.append([len(name_index) - 1, new_file])

        return new_files_index

    def index_target_dir(self, target_dir) -> list[tuple[int, str]]:
        name_index = self._get_name_index()
        changed_files_index = self._get_changed_files_index(name_index)
        new_files_index = self._get_new_files_index(name_index, target_dir)
        self._save_name_index(name_index)
        return changed_files_index + new_files_index

    def update_ir_index(self, need_index) -> None:
        # hwnd作为图数据库，它的节点是不允许更新的；所谓的更新，其实是先删后增
        for idx, fpath in tqdm(need_index, ascii=False, ncols=50):
            fv = self.ir_engine.get_fv(fpath)
            if fv is None:
                continue               
            try:
                self.ir_engine.hnsw_index.mark_deleted(idx)
            except Exception:
                pass

            self.ir_engine.add_fv(fv, idx)
        self.remove_nonexists()
        self.ir_engine.save_index()

    def remove_nonexists(self) -> None:
        name_index = self._get_name_index()
        for idx in tqdm(range(len(name_index)), ascii=False, ncols=50):
            if Path(name_index[idx][0]).exists():
                continue
            try:
                # 对元数据标记为空
                name_index[idx][1] = NOTEXISTS
                self.ir_engine.hnsw_index.mark_deleted(idx)
            except:
                pass
        self._save_name_index(name_index)

    def checkout(self, image_path, exists_index):
        fv = self.ir_engine.get_fv(image_path)
        sim, ids = self.ir_engine.match(fv, self.max_match_count)
        return [(sim[i], exists_index[ids[i]][0]) for i in range(len(ids))]



class QueueStream:
    def __init__(self, queue: Queue):
        self.queue = queue

    def write(self, message):
        clean_message = message.replace('\r', '').replace('\n', '').strip()
        if clean_message:
            self.queue.put(clean_message)

    def flush(self) -> None:
        pass


