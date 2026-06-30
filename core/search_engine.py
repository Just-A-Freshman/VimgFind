from concurrent.futures import ThreadPoolExecutor, as_completed
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

from settings import Setting
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
    def __init__(self, setting: Setting, model_id: str | None = None) -> None:
        self.__search_event = Event()
        self.__search_event.set()
        self.__init_event = Event()
        self.__force_stop_update = False
        self._checkout_status: SearchStatus = SearchStatus.OK
        self.__model_id = model_id or setting.app.current_model
        Thread(target=self.__async_init, args=(setting, ), daemon=True).start()

    def __async_init(self, setting: Setting) -> None:
        cfg = setting.model
        rel_base = Path("config/models") / self.__model_id
        self.__vec_idx_mgr = VectorIndexManager(
            str(rel_base / cfg.vector_index_path),
            cfg.index_capacity,
            cfg.index_space,
            cfg.index_dim
        )
        self.__name_idx_mgr = NameIndexManager(
            rel_base / cfg.name_index_path,
            setting.app.max_match_count
        )
        self.__multimodal_encoder = MultiModalEncoder(
            (rel_base / cfg.vocab_path) if cfg.vocab_path else None,
            (rel_base / cfg.image_encoder_path) if cfg.image_encoder_path else None,
            (rel_base / cfg.text_encoder_path) if cfg.text_encoder_path else None,
            np.array(cfg.mean, dtype=np.float32)[:, None, None],
            np.array(cfg.std, dtype=np.float32)[:, None, None],
            cfg.normalization,
            cfg.image_size,
            cfg.context_length
        )
        self.__init_event.set()

    @property
    def valid_index_count(self) -> int:
        self.__init_event.wait()
        return self.__name_idx_mgr.valid_index_count

    @property
    def checkout_status(self) -> SearchStatus:
        return self._checkout_status

    def __get_changed_files_index(self) -> list[tuple[int, str]]:
        changed_files_index = []
        for idx, [index_file, old_metainfo] in enumerate(self.__name_idx_mgr.name_index):
            if index_file == NameIndexManager.NOTEXISTS:
                continue
            new_metainfo = file_ops.get_metainfo(index_file)
            if old_metainfo != new_metainfo:
                changed_files_index.append((idx, index_file))
        return changed_files_index

    def __get_new_files_index(self, target_dir: str, exclude_rules: list[str] | None = None) -> list[tuple[int, str]]:
        new_files_index = []
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

        if not new_files:
            return []

        for idx, [index_file, _] in enumerate(self.__name_idx_mgr.name_index):
            if index_file == NameIndexManager.NOTEXISTS:
                new_files_index.append((idx, new_files.pop()))
            if len(new_files) == 0:
                break
        for idx, new_file in enumerate(new_files, len(self.__name_idx_mgr.name_index)):
            new_files_index.append((idx, new_file))

        return new_files_index

    def __index_target_dir(self, target_dir, exclude_rules: list[str] | None = None) -> list[tuple[int, str]]:
        changed_files_index = self.__get_changed_files_index()
        new_files_index = self.__get_new_files_index(target_dir, exclude_rules)
        return changed_files_index + new_files_index

    def update_max_match_count(self, max_match_count: int) -> None:
        self.__name_idx_mgr.update_max_match_count(max_match_count)

    def update_index(self, image_dir, max_workers: int = 10, exclude_rules: list[str] | None = None) -> None:
        def _process_item(item) -> tuple[int, str, np.ndarray | None]:
            self.__search_event.wait()
            idx, fpath = item
            if self.__force_stop_update:
                return idx, fpath, None
            image_obj = image_ops.parse_image_from_path(fpath)
            if image_obj is None:
                fv = None
            else:
                fv = self.__multimodal_encoder.encode_image(image_obj)
            return idx, fpath, fv
        self.__init_event.wait()
        need_to_update = self.__index_target_dir(image_dir, exclude_rules)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            pbar = tqdm(total=len(need_to_update), ascii=False, ncols=50)
            futures = [executor.submit(_process_item, item) for item in need_to_update]
            for future in as_completed(futures):
                try:
                    idx, fpath, fv = future.result()
                except Exception as e:
                    logging.error(f"索引线程错误: {e}", exc_info=True)
                    pbar.update(1)
                    continue
                if fv is not None:
                    self.__vec_idx_mgr.add_vector(fv, idx)
                    self.__name_idx_mgr.add_name(fpath, idx)
                pbar.update(1)
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
        for idx, (index_file, _) in enumerate(self.__name_idx_mgr.name_index):
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

        self.stop_update_index()
        try:
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
        finally:
            self.continue_update_index()

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

            if ext_set and Path(file_path).suffix.lower() not in ext_set:
                continue

            if size_min is not None or size_max is not None:
                file_size_mb = Path(file_path).stat().st_size / (1024 * 1024)
                if size_min is not None and file_size_mb < size_min:
                    continue
                if size_max is not None and file_size_mb > size_max:
                    continue

            if folder_filters:
                file_path_obj = Path(file_path)
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

    def stop_update_index(self) -> None:
        self.__search_event.clear()

    def set_force_end_update(self, state: bool) -> None:
        self.__force_stop_update = state

    def continue_update_index(self) -> None:
        self.__search_event.set()

    def destroy(self) -> None:
        self.__search_event.set()
        self.__init_event.set()
