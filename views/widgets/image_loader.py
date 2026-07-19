from __future__ import annotations
from collections import namedtuple
from concurrent.futures import ThreadPoolExecutor
import queue

from PIL import ImageTk, ImageOps

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
                item=item, size=(0, 0), photo=None, error="加载图片失败！"
            ))
        else:
            img = ImageOps.exif_transpose(img) or img
            width, height = img.size
            img.thumbnail((thumbnail_size, thumbnail_size))
            self._result_queue.put(LoaderResult(
                item=item,
                size=(width, height),
                photo=img,
                error=""
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
