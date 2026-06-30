import json
import logging
import os
import tempfile
import threading
import time
import zipfile
import hashlib
from pathlib import Path
from typing import Callable
from urllib.error import URLError
import urllib.request as request
import urllib.error

from settings import Setting, ModelConfig
from utils import file_ops



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
        self.threads = []
        self.part_files = []

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

        if not self.accept_ranges or self.file_size < self.chunk_size:
            self.num_threads = 1
        self.num_threads = min(self.num_threads, self.file_size)

    def _get_ranges(self):
        part_size = self.file_size // self.num_threads
        ranges = []
        for i in range(self.num_threads):
            start = i * part_size
            end = self.file_size - 1 if i == self.num_threads - 1 else (i + 1) * part_size - 1
            ranges.append((start, end))
        return ranges

    def _download_part(self, part_index, start, end) -> None:
        part_file = f"{self.save_path}.part{part_index}"
        self.part_files.append(part_file)

        headers = {'Range': f'bytes={start}-{end}'}
        req = request.Request(self.url, headers=headers)
        downloaded_in_part = 0
        try:
            with request.urlopen(req, timeout=60) as resp:
                with open(part_file, 'wb') as f:
                    while True:
                        chunk = resp.read(self.chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        chunk_len = len(chunk)
                        downloaded_in_part += chunk_len

                        with self.lock:
                            self.downloaded += chunk_len
                            if self.progress_callback:
                                self.progress_callback(self.downloaded, self.file_size)
        except Exception as e:
            if os.path.exists(part_file):
                os.remove(part_file)
            raise RuntimeError(f"线程 {part_index} 下载失败: {e}")

    def _cleanup(self) -> None:
        for part_file in self.part_files:
            if os.path.exists(part_file):
                os.remove(part_file)

    def download(self) -> None:
        self._get_file_info()
        ranges = self._get_ranges()
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

        self._merge_files()
        self._cleanup()

    def _merge_files(self) -> None:
        with open(self.save_path, 'wb') as outfile:
            for part_file in self.part_files:
                with open(part_file, 'rb') as infile:
                    while True:
                        chunk = infile.read(self.chunk_size)
                        if not chunk:
                            break
                        outfile.write(chunk)

    def _verify_checksum(self):
        if self.checksum == "":
            return
        algo, expected_hash = self.checksum
        expected_hash = expected_hash.lower()
        hash_func = hashlib.new(algo)
        with open(self.save_path, 'rb') as f:
            while True:
                data = f.read(self.chunk_size)
                if not data:
                    break
                hash_func.update(data)
        actual_hash = hash_func.hexdigest()
        if actual_hash != expected_hash:
            self._cleanup()
            if os.path.exists(self.save_path):
                os.remove(self.save_path)
            raise RuntimeError(
                f"校验和不匹配: 预期 {expected_hash}，实际 {actual_hash}"
            )




def _fetch_remote_manifest(
    url: str = "",
    cache_path: Path | None = None,
    cache_ttl: int = 3600,
) -> list[dict] | None:
    now = time.time()
    try:
        local_path = Path(__file__).resolve().parent.parent / "models.json"
        if local_path.exists():
            with open(local_path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass

    if cache_path is not None and cache_path.exists():
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cache = json.load(f)
            if now - cache.get("timestamp", 0) < cache_ttl:
                return cache.get("models")
        except (json.JSONDecodeError, IOError):
            pass

    try:
        req = request.Request(
            url,
            headers={"User-Agent": "VimgFind/2.5.1", "Accept": "application/json"},
        )
        with request.urlopen(req, timeout=10) as resp:
            models: list[dict] = json.loads(resp.read().decode("utf-8"))

        if cache_path is not None:
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
    cache_path = setting.models_dir / "_manifest_cache.json"
    installed_ids = setting.get_model_list()
    local_map: dict[str, ModelConfig] = {}
    result: list[ModelConfig] = []

    for mid in installed_ids:
        cfg = setting._load_model_config(mid)
        local_map[mid] = cfg
        result.append(cfg)

    remote_raw = _fetch_remote_manifest(
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
            if not disk_cfg.download_url:
                disk_cfg.download_url = meta.get("download_url", "")
            if not disk_cfg.checksum_sha256:
                disk_cfg.checksum_sha256 = meta.get("checksum_sha256", "")
        else:
            result.append(ModelConfig.from_dict(entry))

    return result



def download_and_extract_zip(
    url: str,
    dest_dir: Path,
    checksum: str = "",
    progress_callback: Callable[[int, int], None] | None = None,
) -> bool:
    temp_dir: Path | None = None
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
        temp_dir = Path(tempfile.mkdtemp(dir=dest_dir))
        zip_path = temp_dir / "model.zip"
        downloader = MultiThreadDownloader(
            url=url,
            save_path=str(zip_path),
            num_threads=16,
            checksum=checksum,
            progress_callback=progress_callback,
        )
        downloader.download()

        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(temp_dir)

        file_ops.merge_dirs(temp_dir, dest_dir, skip_names={"model.zip"})
        return True
    except Exception as e:
        logging.error(f"下载或解压失败: {e}")
        return False
    finally:
        if temp_dir is not None and temp_dir.exists():
            file_ops.rmtree(temp_dir)

