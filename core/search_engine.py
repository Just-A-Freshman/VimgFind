from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from threading import Thread, Event
from pathlib import Path
from typing import Iterator
from re import sub
from enum import Enum
import logging
import os

import numpy as np
from tqdm import tqdm
from PIL import Image

from config.settings import Setting
from .index_manager import VectorIndexManager, NameIndexManager
from .multimodal_encoder import MultiModalEncoder
import utils.file_ops as file_ops
import utils.image_ops as image_ops
import utils.exclude_rules as exclude_rules


class SearchStatus(str, Enum):
    OK = "ok"
    EMPTY_INDEX = "empty_index"
    EMPTY_INPUT = "empty_input"
    ENCODE_FAILED = "encode_failed"
    HNSW_EMPTY = "hnsw_empty"
    NO_RESULTS = "no_results"


THRESHOLD_EPSILON = 1e-3

EXT_FILTER_MAP: dict[str, set[str]] = {
    "PNG": {".png"},
    "JPG/JPEG": {".jpg", ".jpeg"},
    "WebP": {".webp"},
    "GIF": {".gif"},
    "BMP": {".bmp"},
    "TIFF": {".tiff", ".tif"},
}

class SearchTool(object):
    __slots__ = (
        "__init_event", "__force_stop_update", "_checkout_status",
        "__vec_idx_mgr", "__name_idx_mgr", "__multimodal_encoder",
    )

    def __init__(self, setting: Setting) -> None:
        self.__init_event = Event()
        self.__force_stop_update = False
        self._checkout_status: SearchStatus = SearchStatus.OK
        Thread(target=self.__async_init, args=(setting, ), daemon=True).start()

    def __async_init(self, setting: Setting) -> None:
        cfg = setting.model
        self.__name_idx_mgr = NameIndexManager(
            cfg.index.name_index_path,
            setting.app.max_match_count
        )
        self.__vec_idx_mgr = VectorIndexManager(
            cfg.index.vector_index_path,
            cfg.index.index_capacity,
            cfg.index.index_dim,
            len(self.__name_idx_mgr.name_index)
        )
        self.__multimodal_encoder = MultiModalEncoder(cfg.encoder)
        self.__init_event.set()

    @property
    def valid_index_count(self) -> int:
        self.__init_event.wait()
        return self.__name_idx_mgr.valid_index_count

    @property
    def checkout_status(self) -> SearchStatus:
        return self._checkout_status

    def __get_changed_files(self) -> list[str]:
        changed_files = []
        for index_file, old_metainfo in self.__name_idx_mgr.name_index:
            if index_file == NameIndexManager.NOTEXISTS:
                continue
            new_metainfo = file_ops.get_metainfo(index_file)
            if old_metainfo != new_metainfo:
                changed_files.append(index_file)
        return changed_files

    def __get_new_files(self, target_dir: str, exclude_rules: list[str] | None = None) -> list[str]:
        new_files = []
        current_files = file_ops.get_file_iterator(target_dir, exclude_rules)
        existing_files = set(
            file_ops.normalize_path(i[0])
            for i in self.__name_idx_mgr.name_index
        )
        new_files = []
        for file in current_files:
            if self.__force_stop_update:
                break
            if file_ops.normalize_path(file) not in existing_files:
                new_files.append(file)
        return new_files

    def update_max_match_count(self, max_match_count: int) -> None:
        self.__name_idx_mgr.update_max_match_count(max_match_count)

    def update_index(self, image_dir, max_workers: int = 10, exclude_rules: list[str] | None = None) -> None:
        def _process_item(item) -> tuple[str, np.ndarray | None]:
            if self.__force_stop_update:
                return item, None
            image_obj = image_ops.parse_image_from_path(item)
            return item, self.__multimodal_encoder.encode_image(image_obj) if image_obj is not None else None
        
        self.__init_event.wait()
        need_to_update = self.__get_changed_files() + self.__get_new_files(image_dir, exclude_rules)
        if not need_to_update:
            return
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            pbar = tqdm(total=len(need_to_update), ascii=False, ncols=50)
            need_iter = iter(need_to_update)
            pending: set = set()
            window = min(max_workers * 2, len(need_to_update))
            for _ in range(window):
                pending.add(executor.submit(_process_item, next(need_iter)))

            while pending:
                done, pending = wait(pending, return_when=FIRST_COMPLETED)
                for future in done:
                    try:
                        file_path, fv = future.result()
                    except Exception as e:
                        logging.error(f"索引线程错误: {e}", exc_info=True)
                        pbar.update(1)
                        continue
                    if fv is not None:
                        self.__vec_idx_mgr.add_vector(fv, self.__name_idx_mgr.add_name(file_path))
                    pbar.update(1)

                for _ in range(len(done)):
                    try:
                        pending.add(executor.submit(_process_item, next(need_iter)))
                    except StopIteration:
                        break
            pbar.close()

    def remove_duplicate(self) -> None:
        self.__init_event.wait()
        seen_paths: set[str] = set()
        for idx, (file_path, _) in enumerate(self.__name_idx_mgr.name_index):
            if file_path == NameIndexManager.NOTEXISTS:
                continue
            normalized = file_ops.normalize_path(file_path)
            if normalized in seen_paths:
                self.__name_idx_mgr.delete_name(idx)
                self.__vec_idx_mgr.delete_vector(idx)
            else:
                seen_paths.add(normalized)

    def remove_nonexists(self) -> None:
        self.__init_event.wait()
        for idx, (index_file, _) in tqdm(enumerate(self.__name_idx_mgr.name_index), ascii=False, ncols=50):
            if Path(index_file).exists() or index_file == NameIndexManager.NOTEXISTS:
                continue
            self.__name_idx_mgr.delete_name(idx)
            self.__vec_idx_mgr.delete_vector(idx)

    def get_excluded_files(self, rules: list[str], search_dirs: list[str]) -> list[str]:
        self.__init_event.wait()
        rules_obj = exclude_rules.compile_rules(rules)
        if not rules_obj:
            return []

        normalized_dirs = [os.path.normcase(os.path.realpath(d)) for d in search_dirs]

        def _is_excluded(rel_path: str) -> bool:
            if rules_obj.is_excluded(rel_path, is_dir=False):
                return True
            parts = rel_path.replace("\\", "/").split("/")
            for i in range(len(parts)):
                parent = "/".join(parts[:i + 1]) + "/"
                if rules_obj.is_excluded(parent, is_dir=True):
                    return True
            return False

        result: list[str] = []
        for index_file, _ in self.__name_idx_mgr.name_index:
            if index_file == NameIndexManager.NOTEXISTS:
                continue
            for nd in normalized_dirs:
                if index_file.startswith(nd):
                    rel = index_file[len(nd):].lstrip("\\/")
                    if _is_excluded(rel):
                        result.append(index_file)
                    break
        return result

    def remove_files_in_directory(self, directory: str, keep_dirs: list[str] | None = None) -> None:
        self.__init_event.wait()
        directory_path = Path(directory).resolve()
        keep_paths = [Path(d).resolve() for d in (keep_dirs or [])]
        for idx, (index_file, _) in enumerate(self.__name_idx_mgr.name_index):
            if index_file == NameIndexManager.NOTEXISTS:
                continue
            file_path = Path(index_file).resolve()
            if not file_path.is_relative_to(directory_path):
                continue
            if any(file_path.is_relative_to(kp) for kp in keep_paths):
                continue
            self.__name_idx_mgr.delete_name(idx)
            self.__vec_idx_mgr.delete_vector(idx)

    def remove_files(self, file_paths: list[str]) -> None:
        self.__init_event.wait()
        file_set = {file_ops.normalize_path(p) for p in file_paths}
        for idx, (index_file, _) in enumerate(self.__name_idx_mgr.name_index):
            if index_file == NameIndexManager.NOTEXISTS:
                continue
            if file_ops.normalize_path(index_file) in file_set:
                self.__name_idx_mgr.delete_name(idx)
                self.__vec_idx_mgr.delete_vector(idx)

    def checkout(
            self,
            content: Image.Image | str, threshold: float = 0.0,
            file_ext_label: str = "",
            size_min: float | None = None,
            size_max: float | None = None,
            folder_filters: list[str] | None = None
        ) -> Iterator[tuple[str, float]]:
        self.__init_event.wait()
        self._checkout_status = SearchStatus.OK

        if self.__name_idx_mgr.results_count == 0:
            self._checkout_status = SearchStatus.EMPTY_INDEX
            return
        if isinstance(content, str) and content == "":
            self._checkout_status = SearchStatus.EMPTY_INPUT
            return

        fv = self.__multimodal_encoder.encode_image(content) if isinstance(content, Image.Image) \
             else self.__multimodal_encoder.encode_text(sub(r"[\s,]+", "，", content))

        if fv is None:
            logging.warning("搜索失败：编码器返回空特征向量，请检查模型文件是否存在")
            self._checkout_status = SearchStatus.ENCODE_FAILED
            return

        sim_list, ids_list = self.__vec_idx_mgr.match(fv, self.__name_idx_mgr.results_count)
        name_index_len = len(self.__name_idx_mgr.name_index)
        if len(ids_list) == 0:
            logging.error("搜索失败：HNSW向量索引为空，请自行添加索引目录并更新")
            self._checkout_status = SearchStatus.HNSW_EMPTY
            return

        yield from self._filter_and_yield_results(
            ids_list, sim_list, threshold, name_index_len,
            file_ext_label, size_min, size_max, folder_filters
        )

    def _filter_and_yield_results(
            self,
            ids_list: list[int], sim_list: list[float],
            threshold: float, name_index_len: int,
            file_ext_label: str,
            size_min: float | None, size_max: float | None,
            folder_filters: list[str] | None
        ) -> Iterator[tuple[str, float]]:
        ext_set = EXT_FILTER_MAP.get(file_ext_label)
        yielded_count = 0
        threshold -= THRESHOLD_EPSILON

        for img_id, similarity in zip(ids_list, sim_list):
            if similarity < threshold:
                break
            if img_id >= name_index_len:
                logging.warning(f"发现孤立向量ID={img_id}，已自动清理")
                self.__vec_idx_mgr.delete_vector(img_id)
                continue

            file_path = self.__name_idx_mgr.name_index[img_id][0]
            file_path_obj = Path(file_path)

            if ext_set and file_path_obj.suffix.lower() not in ext_set:
                continue

            if size_min is not None or size_max is not None:
                file_size_mb = file_path_obj.stat().st_size / (1024 * 1024)
                if size_min is not None and file_size_mb < size_min:
                    continue
                if size_max is not None and file_size_mb > size_max:
                    continue

            if folder_filters:
                if not any(file_path_obj.is_relative_to(f) for f in folder_filters):
                    continue

            yielded_count += 1
            yield (file_path, similarity)

        if yielded_count == 0:
            self._checkout_status = SearchStatus.NO_RESULTS

    def is_empty_index(self) -> bool:
        return self.__name_idx_mgr.results_count == 0

    def reset_index(self) -> None:
        self.__init_event.wait()
        self.__vec_idx_mgr.reset_index()
        self.__name_idx_mgr.reset_index()

    def save_index(self) -> None:
        self.__init_event.wait()
        try:
            self.__vec_idx_mgr.save_index()
            self.__name_idx_mgr.save_index()
        except Exception as e:
            logging.error(f"保存索引时出现错误: {e}")

    def set_force_end_update(self, state: bool) -> None:
        self.__force_stop_update = state

    def destroy(self, wait: bool = False) -> None:
        if not wait:
            self.__init_event.set()
        else:
            self.__init_event.wait()
        encoder: MultiModalEncoder | None = getattr(self, '_SearchTool__multimodal_encoder', None)
        if encoder is not None:
            encoder.close()
        vec_idx_mgr: VectorIndexManager | None = getattr(self, '_SearchTool__vec_idx_mgr', None)
        if vec_idx_mgr is not None:
            vec_idx_mgr.close()
