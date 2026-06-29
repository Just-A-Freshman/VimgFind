from threading import Thread
from collections import namedtuple
import queue

from PIL import ImageTk, ImageOps

import utils.image_ops as image_ops


LoaderResult = namedtuple("LoaderResult", ["item", "size", "photo", "error"])


class ImageLoader:
    def __init__(self) -> None:
        self.task_queue: queue.Queue[tuple] = queue.Queue()
        self.result_queue: queue.Queue[LoaderResult] = queue.Queue()
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
            except queue.Empty:
                continue
            img = image_ops.parse_image_from_path(image_path)
            if img is None:
                self.result_queue.put(LoaderResult(
                    item=item, size=(0, 0), photo=None, error="加载图片失败！"
                ))
            else:
                img = ImageOps.exif_transpose(img) or img
                width, height = img.size
                img.thumbnail((thumbnail_size, thumbnail_size))
                self.result_queue.put(LoaderResult(
                    item=item,
                    size=(width, height),
                    photo=img,
                    error=""
                ))
            self.task_queue.task_done()

    def get_results(self) -> list[LoaderResult]:
        results = []
        while not self.result_queue.empty():
            result = self.result_queue.get_nowait()
            photo = ImageTk.PhotoImage(result.photo) if result.photo is not None else None
            results.append(LoaderResult(
                item=result.item, size=result.size, photo=photo, error=result.error
            ))
        return results

    def stop(self) -> None:
        self.running = False
        for thread in self.threads:
            thread.join(timeout=1)
