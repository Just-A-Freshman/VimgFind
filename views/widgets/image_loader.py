from __future__ import annotations

import logging
from collections import namedtuple
import queue

from concurrent.futures import ThreadPoolExecutor
from PIL import ImageTk, ImageOps

from utils.i18n import _
import utils.image_ops as image_ops


LoaderResult = namedtuple("LoaderResult", ["item", "size", "photo", "error"])


class ImageLoader:
    __slots__ = ("_executor", "_result_queue", "_running")

    def __init__(self) -> None:
        self._result_queue: queue.Queue[LoaderResult] = queue.Queue()
        self._executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="img_loader")
        self._running = True

    def add_task(self, item: str, image_path: str, thumbnail_size: int) -> None:
        self._executor.submit(self._process_one, item, image_path, thumbnail_size)

    def _process_one(self, item: str, image_path: str, thumbnail_size: int) -> None:
        img = image_ops.parse_image_from_path(image_path)
        if img is None:
            self._result_queue.put(LoaderResult(
                item=item, size=(0, 0), photo=None, error=_("加载图片失败！")
            ))
            return
        try:
            width, height = img.size
            if img.mode == 'P':
                img = img.convert('RGBA')
            elif img.format in ('JPEG', 'MPO') and max(img.size) > thumbnail_size * 10:
                img.draft('RGB', (thumbnail_size * 2, thumbnail_size * 2))
            img = ImageOps.exif_transpose(img) or img
            img.thumbnail((thumbnail_size, thumbnail_size))
            self._result_queue.put(LoaderResult(item=item, size=(width, height), photo=img, error=""))
        except Exception as e:
            logging.exception(f"图片处理失败:{image_path}，错误原因：{str(e)}")
            self._result_queue.put(LoaderResult(
                item=item, size=(0, 0), photo=None, error=_("图片处理失败！")
            ))

    def get_results(self) -> list[LoaderResult]:
        results = []
        while not self._result_queue.empty():
            result = self._result_queue.get_nowait()
            photo = ImageTk.PhotoImage(result.photo) if result.photo is not None else None
            results.append(LoaderResult(
                item=result.item, size=result.size, photo=photo, error=result.error
            ))
        return results

    def stop(self) -> None:
        self._running = False
        self._executor.shutdown(wait=False, cancel_futures=True)
