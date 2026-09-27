from __future__ import annotations

from enum import Enum, auto
from pathlib import Path
from typing import Callable
import urllib.request as request
import ipaddress
import logging
import os
import socket
import urllib.parse
import tempfile
import threading
import time
import zipfile

from . import file_ops


DEFAULT_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'


def fetch_url(
    url: str,
    timeout: int = 10,
    headers: dict | None = None,
    method: str | None = None,
    validate: bool = False,
):
    if validate and not validate_url_safe(url):
        raise ValueError(f"不安全的 URL，已拦截: {url}")
    headers = dict(headers or {})
    headers.setdefault('User-Agent', DEFAULT_USER_AGENT)
    req = request.Request(url, headers=headers, method=method)
    return request.urlopen(req, timeout=timeout)


def validate_url_safe(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        logging.warning(f"不支持的URL协议: {parsed.scheme}")
        return False
    try:
        addr = socket.getaddrinfo(parsed.hostname, None)
    except Exception as e:
        logging.warning(f"URL域名解析失败: {parsed.hostname}, {e}")
        return False
    for _, _, _, _, sockaddr in addr:
        ip = sockaddr[0]
        if ipaddress.ip_address(ip).is_private:
            logging.warning(f"禁止访问私有IP: {ip}")
            return False
        if ipaddress.ip_address(ip).is_loopback:
            logging.warning(f"禁止访问回环地址: {ip}")
            return False
        if ipaddress.ip_address(ip).is_link_local:
            logging.warning(f"禁止访问链路本地地址: {ip}")
            return False
    return True


class MultiThreadDownloader:
    def __init__(
            self, 
            url, 
            save_path, 
            num_threads=32, 
            chunk_size=262144, 
            checksum: str = "",
            progress_callback=None,
            validate: bool = True,
            max_retries: int = 4,
            retry_backoff: float = 1.0,
        ) -> None:
        self.url = url
        self.save_path = save_path
        self.num_threads = num_threads
        self.chunk_size = chunk_size
        self.checksum = checksum
        self.progress_callback = progress_callback
        self.validate = validate
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff

        self.file_size = 0
        self.accept_ranges = False
        self.downloaded = 0
        self.error_lock = threading.Lock()
        self.threads = []
        self.part_files = []
        self.ranges = []
        self._pending = []
        self._queue_lock = threading.Lock()
        self._part_done = []
        self._url: str = url
        self._resolve_lock = threading.Lock()
        self._resolved_at = 0.0
        self._has_error = False
        self._error_msg = ""
        self._pause_event = threading.Event()
        self._pause_event.set()  # set = running, cleared = paused
        self._cancel_event = threading.Event()

    def _get_file_info(self) -> None:
        """一次请求拿到直链、总大小、是否支持分片。

        用 `Range: bytes=0-0` 而不是 HEAD：HEAD 在 github.com 上经常被直接重置；
        302 之后的 CDN 主机才是真正下载的地方 —— 记下它，所有分片都直接连 CDN，
        不用每个线程各自去 github.com 握一次手（原来就是这么整体失败的）。
        """
        last: Exception | None = None
        for attempt in range(self.max_retries + 1):
            if self._cancel_event.is_set():
                raise RuntimeError("下载已取消")
            try:
                with fetch_url(
                    self.url, timeout=10, headers={'Range': 'bytes=0-0'}, 
                    validate=self.validate
                ) as resp:
                    geturl = getattr(resp, 'geturl', None)
                    if callable(geturl):
                        self._url = geturl() or self.url  # type: ignore
                    content_range = resp.headers.get('Content-Range', '')
                    if '/' in content_range:
                        self.file_size = int(content_range.rsplit('/', 1)[1])
                        self.accept_ranges = True
                    else:
                        self.file_size = int(resp.headers.get('Content-Length', 0) or 0)
                        self.accept_ranges = False
                if self.file_size == 0:
                    raise RuntimeError("无法获取文件大小，下载取消")
                self._resolved_at = time.time()
                break
            except Exception as e:
                last = e
                if attempt < self.max_retries:
                    self._sleep(self.retry_backoff * 2 ** attempt)
        else:
            raise RuntimeError(f"无法获取文件信息（重试 {self.max_retries} 次失败）: {last}")

        if self.validate and self._url != self.url and not validate_url_safe(self._url):
            raise ValueError(f"不安全的 URL，已拦截: {self._url}")

        if not self.accept_ranges or self.file_size < self.chunk_size * 2:
            self.num_threads = 1

        max_possible = max(1, self.file_size // self.chunk_size)
        self.num_threads = min(self.num_threads, max_possible, 64)

    def _sleep(self, seconds: float) -> None:
        """退避睡眠，取消/继续能立刻打断，不会把退出拖成 1+2+4+8 秒。"""
        self._cancel_event.wait(seconds)
        self._pause_event.wait()

    def _re_resolve(self) -> None:
        """签名直链失效（401/403）时才换一条，且只让一个线程去解析，其余等它。"""
        with self._resolve_lock:
            if time.time() - self._resolved_at < 1.0:
                return
            logging.warning("下载直链失效，重新解析")
            try:
                self._get_file_info()
            except RuntimeError as e:
                logging.warning(f"重新解析下载直链失败: {e}")

    def _get_ranges(self):
        """把文件切成远多于线程数的小块，谁下完谁接着领 —— 不用等最慢那一个。

        静态均分时实测过一次：15/16 片 55s 就完了，一片卡着拖到 111s（固定 16 份、
        join 等最慢的）。块数取线程数的 4 倍，代价只是多几次 TLS 握手。
        上限 8MB：每个连接的“快段”只有开头那几 MB（之后掉到 ~0.1MB/s）。
        """
        if not self.accept_ranges:
            return [(0, self.file_size - 1)]

        part_size = min(8 << 20, max(self.chunk_size, -(-self.file_size // (self.num_threads * 4))))
        ranges = []
        start = 0
        while start < self.file_size:
            end = min(start + part_size, self.file_size) - 1
            ranges.append((start, end))
            start = end + 1
        return ranges

    def pause(self) -> None:
        self._pause_event.clear()

    def resume(self) -> None:
        self._pause_event.set()

    def cancel(self) -> None:
        self._cancel_event.set()
        self._pause_event.set()  # unblock paused threads so they can exit

    def _worker(self) -> None:
        """领一块下一块：早下完的线程把剩下的活分掉，不让最慢的那条连接定总时长。"""
        while True:
            with self._queue_lock:
                if not self._pending:
                    return
                index = self._pending.pop(0)
            self._download_part(index, *self.ranges[index])

    def _part_size(self, part_file: str, length: int) -> int:
        """这一块手上已有多少字节；比该有的长就截回去，别把多余字节拼进最终文件。"""
        if not os.path.exists(part_file):
            return 0
        size = os.path.getsize(part_file)
        if size > length:
            os.truncate(part_file, length)
            size = length
        return size

    def _fetch_into(self, part_file: str, first: int, end: int, part_index: int) -> None:
        """从 first 字节续写这一块（分块级续传）。"""
        headers = {'Range': f'bytes={first}-{end}'}
        with fetch_url(self._url, timeout=8, headers=headers, validate=False) as resp:
            status = getattr(resp, "status", 206)
            content_range = resp.headers.get("Content-Range", "")
            if content_range and not content_range.startswith(f"bytes {first}-"):
                raise RuntimeError(f"服务器返回的范围不对：{content_range}，期望从 {first} 开始")
            if status == 200 and (first != 0 or end != self.file_size - 1):
                raise RuntimeError(f"服务器忽略了 Range（回了 200 整包），分片 {first}-{end} 不可信")
            with open(part_file, 'ab') as f:
                while True:
                    self._pause_event.wait()
                    if self._cancel_event.is_set() or self._has_error:
                        return
                    chunk = resp.read1(self.chunk_size) if hasattr(resp, "read1") else resp.read(self.chunk_size)
                    if not chunk:
                        return
                    f.write(chunk)
                    self._count(part_index, len(chunk))

    def _count(self, part_index: int, nbytes: int) -> None:
        self._part_done[part_index] += nbytes
        self.downloaded = sum(self._part_done)
        if self.progress_callback:
            self.progress_callback(self.downloaded, self.file_size)

    def _download_part(self, part_index, start, end) -> None:
        """下完这一块，失败就带着已有字节重连续传 —— 一次断线不该作废整包。"""
        part_file = self.part_files[part_index]
        length = end - start + 1
        last: Exception | None = None

        for attempt in range(self.max_retries + 1):
            if self._cancel_event.is_set() or self._has_error:
                return
            written = self._part_size(part_file, length)
            if written == length:
                return
            try:
                self._fetch_into(part_file, start + written, end, part_index)
            except Exception as e:
                last = e
                if getattr(e, 'code', None) in (401, 403):
                    self._re_resolve()
            if self._part_size(part_file, length) == length:
                return
            if last is None:
                last = RuntimeError("连接提前结束")
            logging.warning(f"分片 {part_index} 第 {attempt + 1}/{self.max_retries + 1} 次尝试失败: {last}")
            if attempt < self.max_retries:
                self._sleep(self.retry_backoff * 2 ** attempt)

        with self.error_lock:
            if not self._has_error:
                self._has_error = True
                self._error_msg = f"分片 {part_index} 下载失败（重试 {self.max_retries} 次）: {last}"

    def _prepare_parts(self, ranges) -> None:
        """上次留下的分片直接当续传起点，进度也一并算上（否则进度条会从 0 开始）。

        分片名带起始偏移：偏移对得上就能接着用（同一份文件的字节总在同一个位置），
        对不上（换了文件/切法）的直接删掉，不会拿旧字节拼出错包。
        """
        self.ranges = ranges
        self.part_files = [f"{self.save_path}.part{start}" for start, _ in ranges]
        self._part_done = [0] * len(ranges)
        expected = set(self.part_files)
        base = Path(self.save_path)
        for stale in base.parent.glob(base.name + ".part*"):
            if str(stale) not in expected:
                os.remove(stale)
        for i, (part_file, (start, end)) in enumerate(zip(self.part_files, ranges)):
            self._part_done[i] = self._part_size(part_file, end - start + 1)
        if not self.accept_ranges:
            for i, (part_file, (start, end)) in enumerate(zip(self.part_files, ranges)):
                if 0 < self._part_done[i] < end - start + 1:
                    os.remove(part_file)
                    self._part_done[i] = 0
        self.downloaded = sum(self._part_done)
        self._pending = list(range(len(ranges)))

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
        self._prepare_parts(ranges)

        self.threads.clear()
        self._has_error = False
        self._error_msg = ""
        if self.progress_callback:
            self.progress_callback(self.downloaded, self.file_size)

        for _ in range(min(self.num_threads, len(ranges))):
            t = threading.Thread(target=self._worker, daemon=True)
            self.threads.append(t)
            t.start()

        for t in self.threads:
            t.join()

        if self._cancel_event.is_set():
            raise RuntimeError("下载已取消")

        if self._has_error:
            raise RuntimeError(self._error_msg)

        # 再确认一遍每块都到位：少了/短了就报错，绝不拿不完整的块去拼接
        missing = [i for i, (f, (s, e)) in enumerate(zip(self.part_files, self.ranges))
                   if self._part_size(f, e - s + 1) != e - s + 1]
        if missing:
            raise RuntimeError(f"有 {len(missing)} 块没下完（{missing[:5]}），下载中止")

        self._merge_files()
        self._cleanup()
        
        if not self.checksum:
            return
        if not file_ops.verify_file_sha256(self.save_path, self.checksum):
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
        self._cancel_requested = False
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
        _last_ui = 0.0
        def wrapped(downloaded: int, total: int) -> None:
            nonlocal _last_ui
            now = time.time()
            elapsed = now - self._last_time
            delta = downloaded - self._last_dl
            if elapsed > 0:
                self.speed = delta / elapsed
            self._last_dl = downloaded
            self._last_time = now
            self.downloaded_bytes = downloaded
            self.total_bytes = total
            if self._progress_callback and (now - _last_ui >= 0.1 or downloaded >= total):
                _last_ui = now
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
            if self._cancel_requested:
                self._downloader.cancel()
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
            if self._state == DownloadState.DOWNLOADING and self._downloader and not self._cancel_requested:
                self._downloader.pause()
                self._state = DownloadState.PAUSED

    def resume(self) -> None:
        with self._lock:
            if self._state == DownloadState.PAUSED and self._downloader:
                self._downloader.resume()
                self._state = DownloadState.DOWNLOADING

    def cancel(self) -> None:
        with self._lock:
            self._cancel_requested = True
            if self._downloader:
                self._downloader.cancel()

    @property
    def state(self) -> DownloadState:
        with self._lock:
            return self._state


