import json
import logging
import os
import tempfile
import threading
import time
import zipfile
import hashlib
from pathlib import Path
from typing import Callable, Any
from urllib.error import URLError
import urllib.request as request
import urllib.error

from enum import Enum, auto

from config.types import ModelConfig
from config.settings import Setting
from . import file_ops



def verify_zip_sha256(zip_path: Path, expected: str) -> bool:
    try:
        algo, expected_hash = expected.split(":", 1)
    except ValueError:
        return False
    if algo != "sha256":
        return False
    sha256 = hashlib.sha256()
    with open(zip_path, "rb") as f:
        while True:
            data = f.read(8192)
            if not data:
                break
            sha256.update(data)
    return sha256.hexdigest() == expected_hash.lower()



def validate_unknown_zip(zip_path: Path, model_id: str) -> ModelConfig:
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            namelist = zf.namelist()

            onnx_files = [n for n in namelist if n.endswith(".onnx")]
            if not onnx_files:
                raise AssertionError("无法识别的模型包：未找到 ONNX 模型文件（.onnx）。")

            if "model.json" not in namelist:
                raise AssertionError("无法识别的模型包：未找到 model.json 配置文件。")

            with zf.open("model.json") as f:
                raw = json.loads(f.read().decode("utf-8"))

            mc = raw.get("model_config") or {}
            image_path = mc.get("image_encoder_path", "") or ""
            text_path = mc.get("text_encoder_path", "") or ""

            if image_path and image_path not in namelist:
                raise AssertionError(f"校验失败：model.json 中的 image_encoder_path「{image_path}」在 zip 包中不存在。")
            if text_path and text_path not in namelist:
                raise AssertionError(f"校验失败：model.json 中的 text_encoder_path「{text_path}」在 zip 包中不存在。")

            raw["meta_info"] = raw.get("meta_info") or {"id": model_id, "name": model_id}
            return ModelConfig.from_dict(raw)

    except (zipfile.BadZipFile, json.JSONDecodeError) as e:
        raise AssertionError(f"无法读取模型包：{e}")



def read_manifest_cache(cache_path: Path) -> dict[str, Any]:
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError, FileNotFoundError):
        return {}



def fetch_remote_manifest(
    url: str,
    cache_path: Path,
    cache_ttl: int = 3600,
) -> list[dict] | None:
    now = time.time()
    cache = read_manifest_cache(cache_path)
    if len(cache) == 0:
        return
    if now - cache.get("timestamp", 0) < cache_ttl:
        return cache.get("models")
    try:
        req = request.Request(url, headers={"Accept": "application/json"},)
        with request.urlopen(req, timeout=10) as resp:
            models: list[dict] = json.loads(json.loads(resp.read().decode("utf-8"))["raw_content"])
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump({"timestamp": now, "models": models}, f, indent=2)
        except IOError:
            pass
        return models
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError) as e:
        logging.warning(f"获取远程模型清单失败: {e}")
        return None
    


def is_installed(setting: Setting, model_id: str) -> bool:
    model_dir = setting.models_dir / model_id
    return model_dir.is_dir() and (model_dir / "model.json").is_file()



def get_available_models(setting: Setting) -> list[ModelConfig]:
    cache_path = setting.manifest_cache
    installed_ids = setting.get_model_list()
    local_map: dict[str, ModelConfig] = {}
    result: list[ModelConfig] = []

    for mid in installed_ids:
        cfg = setting.load_model_config(mid)
        local_map[mid] = cfg
        result.append(cfg)

    remote_raw = fetch_remote_manifest(
        url=setting.app.remote_manifest_url,
        cache_path=cache_path,
        cache_ttl=setting.app.cache_ttl
    )
    if not remote_raw:
        return result
    for entry in remote_raw:
        meta = entry.get("meta_info") or {}
        mid = meta.get("id")
        if not mid:
            continue
        if mid in local_map:
            disk_cfg = local_map[mid]
            if not disk_cfg.meta.download_url:
                disk_cfg.meta.download_url = meta.get("download_url", "")
            if not disk_cfg.meta.checksum_sha256:
                disk_cfg.meta.checksum_sha256 = meta.get("checksum_sha256", "")
        else:
            result.append(ModelConfig.from_dict(entry))

    return result




class MultiThreadDownloader:
    def __init__(
            self, 
            url, 
            save_path, 
            num_threads=32, 
            chunk_size=8192, 
            checksum: str = "",
            progress_callback=None
        ) -> None:
        self.url = url
        self.save_path = save_path
        self.num_threads = num_threads
        self.chunk_size = chunk_size
        self.checksum = checksum
        self.progress_callback = progress_callback

        self.file_size = 0
        self.accept_ranges = False
        self.downloaded = 0
        self.lock = threading.Lock()
        self.error_lock = threading.Lock()
        self.threads = []
        self.part_files = []
        self._has_error = False
        self._error_msg = ""
        self._pause_event = threading.Event()
        self._pause_event.set()  # set = running, cleared = paused
        self._cancel_event = threading.Event()

    def _get_file_info(self) -> None:
        req = request.Request(self.url, method='HEAD')
        try:
            with request.urlopen(req, timeout=30) as resp:
                self.file_size = int(resp.headers.get('Content-Length', 0))
                self.accept_ranges = resp.headers.get('Accept-Ranges', '').lower() == 'bytes'
        except URLError as e:
            raise RuntimeError(f"无法获取文件信息: {e}")

        if self.file_size == 0:
            raise RuntimeError("无法获取文件大小，下载取消")

        if not self.accept_ranges or self.file_size < self.chunk_size * 2:
            self.num_threads = 1
            
        max_possible = max(1, self.file_size // self.chunk_size)
        self.num_threads = min(self.num_threads, max_possible, 64)

    def _get_ranges(self):
        part_size = self.file_size // self.num_threads
        ranges = []
        for i in range(self.num_threads):
            start = i * part_size
            end = self.file_size - 1 if i == self.num_threads - 1 else (i + 1) * part_size - 1
            ranges.append((start, end))
        return ranges

    def pause(self) -> None:
        self._pause_event.clear()

    def resume(self) -> None:
        self._pause_event.set()

    def cancel(self) -> None:
        self._cancel_event.set()
        self._pause_event.set()  # unblock paused threads so they can exit

    def _download_part(self, part_index, start, end) -> None:
        if self._has_error:
            return
        if self._cancel_event.is_set():
            return
        part_file = f"{self.save_path}.part{part_index}"
        with self.lock:
            self.part_files.append(part_file)

        headers = {'Range': f'bytes={start}-{end}'}
        req = request.Request(self.url, headers=headers)
        try:
            with request.urlopen(req, timeout=60) as resp:
                with open(part_file, 'wb') as f:
                    while True:
                        if self._has_error:
                            return
                        self._pause_event.wait()  # blocks when paused
                        if self._cancel_event.is_set():
                            return
                        chunk = resp.read(self.chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        with self.lock:
                            self.downloaded += len(chunk)
                            if self.progress_callback:
                                self.progress_callback(self.downloaded, self.file_size)
        except Exception as e:
            with self.error_lock:
                if not self._has_error:
                    self._has_error = True
                    self._error_msg = f"线程 {part_index} 下载失败: {e}"
            if os.path.exists(part_file):
                try:
                    os.remove(part_file)
                except OSError:
                    pass

    @property
    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def _cleanup(self) -> None:
        for part_file in self.part_files:
            if os.path.exists(part_file):
                os.remove(part_file)

    def download(self) -> None:
        self._get_file_info()
        ranges = self._get_ranges()

        self.threads.clear()
        self.part_files.clear()
        self.downloaded = 0
        self._has_error = False
        self._error_msg = ""

        for i, (start, end) in enumerate(ranges):
            t = threading.Thread(
                target=self._download_part,
                args=(i, start, end),
                daemon=True
            )
            self.threads.append(t)
            t.start()

        for t in self.threads:
            t.join()

        if self._cancel_event.is_set():
            self._cleanup()
            raise RuntimeError("下载已取消")

        if self._has_error:
            self._cleanup()
            raise RuntimeError(self._error_msg)

        self._merge_files()
        self._cleanup()
        
        if not self.checksum:
            return
        if not verify_zip_sha256(self.save_path, self.checksum):
            if os.path.exists(self.save_path):
                os.remove(self.save_path)
            raise RuntimeError(f"校验和不匹配: 预期 {self.checksum}")

    def _merge_files(self) -> None:
        with open(self.save_path, 'wb') as outfile:
            for part_file in self.part_files:
                with open(part_file, 'rb') as infile:
                    while True:
                        chunk = infile.read(self.chunk_size)
                        if not chunk:
                            break
                        outfile.write(chunk)
        if self.progress_callback:
            self.progress_callback(self.file_size, self.file_size)



class DownloadState(Enum):
    IDLE = auto()
    DOWNLOADING = auto()
    PAUSED = auto()
    CANCELLED = auto()
    COMPLETED = auto()
    ERROR = auto()


class DownloadTask:
    def __init__(
        self,
        url: str,
        dest_dir: Path,
        model_id: str,
        checksum: str = "",
    ) -> None:
        self.url = url
        self.dest_dir = dest_dir
        self.model_id = model_id
        self.checksum = checksum
        self._state = DownloadState.IDLE
        self._downloader: MultiThreadDownloader | None = None
        self._error_msg = ""
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._progress_callback: Callable | None = None
        self.downloaded_bytes = 0
        self.total_bytes = 0
        self.speed = 0.0
        self._last_dl = 0
        self._last_time = time.time()

    def start(self, progress_callback: Callable[[int, int, float], None] | None = None) -> None:
        self._progress_callback = progress_callback
        self._state = DownloadState.DOWNLOADING
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _make_progress_wrapper(self) -> Callable[[int, int], None]:
        def wrapped(downloaded: int, total: int) -> None:
            now = time.time()
            elapsed = now - self._last_time
            delta = downloaded - self._last_dl
            if elapsed > 0:
                self.speed = delta / elapsed
            self._last_dl = downloaded
            self._last_time = now
            self.downloaded_bytes = downloaded
            self.total_bytes = total
            if self._progress_callback:
                self._progress_callback(downloaded, total, self.speed)
        return wrapped

    def _run(self) -> None:
        temp_dir: Path | None = None
        try:
            self.dest_dir.mkdir(parents=True, exist_ok=True)
            temp_dir = Path(tempfile.mkdtemp(dir=self.dest_dir))
            zip_path = temp_dir / "model.zip"

            self._downloader = MultiThreadDownloader(
                url=self.url,
                save_path=str(zip_path),
                num_threads=16,
                checksum=self.checksum,
                progress_callback=self._make_progress_wrapper(),
            )
            self._downloader.download()

            if self._downloader.is_cancelled:
                self._state = DownloadState.CANCELLED
                return

            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(temp_dir)
            file_ops.merge_dirs(temp_dir, self.dest_dir, skip_names={"model.zip"})
            self._state = DownloadState.COMPLETED
        except RuntimeError as e:
            msg = str(e)
            if msg == "下载已取消":
                self._state = DownloadState.CANCELLED
            else:
                self._error_msg = msg
                self._state = DownloadState.ERROR
            logging.error(f"下载任务失败: {e}")
        except Exception as e:
            self._error_msg = str(e)
            self._state = DownloadState.ERROR
            logging.error(f"下载任务异常: {e}", exc_info=True)
        finally:
            if temp_dir is not None and temp_dir.exists():
                file_ops.rmtree(temp_dir)

    def pause(self) -> None:
        with self._lock:
            if self._state == DownloadState.DOWNLOADING and self._downloader:
                self._downloader.pause()
                self._state = DownloadState.PAUSED

    def resume(self) -> None:
        with self._lock:
            if self._state == DownloadState.PAUSED and self._downloader:
                self._downloader.resume()
                self._state = DownloadState.DOWNLOADING

    def cancel(self) -> None:
        with self._lock:
            if self._downloader:
                self._downloader.cancel()
            self._state = DownloadState.CANCELLED

    @property
    def state(self) -> DownloadState:
        with self._lock:
            return self._state



