from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from threading import Event
from enum import Enum
from pathlib import Path
from re import sub
from typing import Iterator
import logging
import random

from PIL import Image
from tqdm import tqdm
import numpy as np

from .index_manager import VectorIndexManager, NameIndexManager
from .multimodal_encoder import MultiModalEncoder
from config.settings import Setting
import utils.exclude_rules as exclude_rules
import utils.file_ops as file_ops
import utils.image_ops as image_ops
import utils.decorators as decorators


class SearchStatus(str, Enum):
    OK = "ok"
    EMPTY_INDEX = "empty_index"
    EMPTY_INPUT = "empty_input"
    ENCODE_FAILED = "encode_failed"
    NO_RESULTS = "no_results"
    PARTIAL_OMITTED = "partialOmitted"


THRESHOLD_EPSILON = 1e-3


class SearchTool:
    __slots__ = (
        "__init_event", "force_stop_update", "__checkout_status",
        "__vec_idx_mgr", "__name_idx_mgr", "__multimodal_encoder", "__setting",
    )

    def __init__(self, setting: Setting) -> None:
        self.__init_event = Event()
        self.__checkout_status: SearchStatus = SearchStatus.OK
        self.__setting = setting
        self.force_stop_update: bool = False
        self.__async_init()

    @decorators.send_task
    def __async_init(self) -> None:
        self.__name_idx_mgr = NameIndexManager(
            self.__setting.model.index.name_index_path,
            self.__setting.app.max_match_count
        )
        self.__vec_idx_mgr = VectorIndexManager(
            self.__setting.model.index.vector_index_path,
            self.__setting.model.index.index_capacity,
            self.__setting.model.index.index_dim,
            len(self.__name_idx_mgr.name_index)
        )
        self.__multimodal_encoder = MultiModalEncoder(self.__setting.model.encoder)
        self.__init_event.set()

    @property
    def valid_index_count(self) -> int:
        self.__init_event.wait()
        return self.__name_idx_mgr.valid_index_count

    @property
    def total_index_count(self) -> int:
        return len(self.__name_idx_mgr.name_index)
    
    @property
    def checkout_status(self) -> SearchStatus:
        return self.__checkout_status
    
    def __get_changed_files(self, target_dir: str) -> list[str]:
        changed_files = []
        for idx, (index_file, old_metainfo) in enumerate(self.__name_idx_mgr.name_index):
            if index_file == NameIndexManager.NOTEXISTS:
                continue
            if not file_ops.is_path_under(index_file, target_dir):
                continue
            new_metainfo = file_ops.get_metainfo(index_file)
            if old_metainfo != new_metainfo:
                self.__name_idx_mgr.name_index[idx][1] = new_metainfo
                changed_files.append(index_file)
        return changed_files

    def __get_new_files(self, target_dir: str, exclude_rules: list[str] | None = None) -> list[str]:
        new_files = []
        current_files = file_ops.get_file_iterator(target_dir, exclude_rules)
        existing_files = set(i[0] for i in self.__name_idx_mgr.name_index if i[0] != NameIndexManager.NOTEXISTS)
        new_files = []
        for file in current_files:
            if self.force_stop_update:
                break
            if file_ops.fast_normalize(file) not in existing_files:
                new_files.append(file)
        return new_files

    def verify_index_match(self, sample_count: int = 3) -> bool:
        valid_entries = [
            (idx, fpath) for idx, (fpath, _) in enumerate(self.__name_idx_mgr.name_index)
            if fpath != NameIndexManager.NOTEXISTS
        ]
        if len(valid_entries) < sample_count:
            return False

        samples = random.sample(valid_entries, sample_count)
        for idx, fpath in samples:
            image_obj = image_ops.parse_image_from_path(fpath)
            if image_obj is None:
                return False
            new_fv = self.__multimodal_encoder.encode_image(image_obj)
            if new_fv is None:
                return False
            stored_fv = self.__vec_idx_mgr.get_items([idx])[0]
            if len(new_fv) != len(stored_fv):
                logging.info(
                    f"模型维度不匹配: new_dim={len(new_fv)}, stored_dim={len(stored_fv)}，触发硬重建"
                )
                return False
            similarity = float(np.dot(new_fv, stored_fv))
            if similarity < 1.0 - 1e-6:
                logging.info(
                    f"模型校验不匹配：{Path(fpath).name} "
                    f"cosine_similarity={similarity:.8f}，触发硬重建"
                )
                return False
        return True

    def update_max_match_count(self, max_match_count: int) -> None:
        self.__name_idx_mgr.update_max_match_count(max_match_count)

    def update_index(
            self, 
            image_dirs: list[str], 
            max_workers: int, 
            exclude_rules: list[str],
            progress_bar: tqdm
        ) -> None:
        def _process_item(item: str) -> tuple[str, np.ndarray | None]:
            if self.force_stop_update:
                return item, None
            image_obj = image_ops.parse_image_from_path(item)
            return item, self.__multimodal_encoder.encode_image(image_obj) if image_obj is not None else None
        
        self.__init_event.wait()
        for image_dir in image_dirs:
            dir_files = self.__get_changed_files(image_dir) + self.__get_new_files(image_dir, exclude_rules)
            if not dir_files or self.force_stop_update:
                continue

            progress_bar.total += len(dir_files)
            
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                need_iter = iter(dir_files)
                pending: set = set()
                window = min(max_workers * 2, len(dir_files))
                for _ in range(window):
                    pending.add(executor.submit(_process_item, next(need_iter)))

                while pending:
                    done, pending = wait(pending, return_when=FIRST_COMPLETED)
                    for future in done:
                        try:
                            file_path, fv = future.result()
                        except Exception as e:
                            logging.error(f"索引线程错误: {e}", exc_info=True)
                            progress_bar.update(1)
                            continue
                        if fv is not None:
                            self.__vec_idx_mgr.add_vector(fv, self.__name_idx_mgr.add_name(file_path))
                        progress_bar.update(1)

                    for _ in range(len(done)):
                        try:
                            pending.add(executor.submit(_process_item, next(need_iter)))
                        except StopIteration:
                            break
        progress_bar.close()

    def remove_duplicate(self) -> None:
        self.__init_event.wait()
        seen_paths: set[str] = set()
        for idx, (file_path, _) in enumerate(self.__name_idx_mgr.name_index):
            if file_path == NameIndexManager.NOTEXISTS:
                continue
            if file_path in seen_paths:
                self.__name_idx_mgr.delete_name(idx)
                self.__vec_idx_mgr.delete_vector(idx)
            else:
                seen_paths.add(file_path)

    def remove_nonexists(self) -> None:
        self.__init_event.wait()
        for idx, (index_file, _) in tqdm(enumerate(self.__name_idx_mgr.name_index), ascii=False, ncols=50):
            if Path(index_file).exists() or index_file == NameIndexManager.NOTEXISTS:
                continue
            self.__name_idx_mgr.delete_name(idx)
            self.__vec_idx_mgr.delete_vector(idx)

    def get_excluded_files(self, rules: list[str], search_dirs: list[str]) -> list[str]:
        self.__init_event.wait()

        if not rules:
            return []

        rules_obj = exclude_rules.compile_rules(rules)
        if not rules_obj:
            return []

        normalized_dirs = [file_ops.fast_normalize(d) for d in search_dirs]
        result: list[str] = []

        for index_file, _ in self.__name_idx_mgr.name_index:
            if index_file == NameIndexManager.NOTEXISTS:
                continue

            target_dir = next((nd for nd in normalized_dirs if file_ops.is_path_under(index_file, nd)), None)
            if target_dir is None:
                result.append(index_file)
                continue

            try:
                if rules_obj.should_skip_file(index_file, target_dir):
                    result.append(index_file)
            except OSError:
                continue

        return result

    def remove_files_in_directory(self, directory: str, keep_dirs: list[str] | None = None) -> None:
        self.__init_event.wait()
        for idx, (index_file, _) in enumerate(self.__name_idx_mgr.name_index):
            if index_file == NameIndexManager.NOTEXISTS:
                continue
            if not file_ops.is_path_under(index_file, directory):
                continue
            if any(file_ops.is_path_under(index_file, kp) for kp in (keep_dirs or [])):
                continue
            self.__name_idx_mgr.delete_name(idx)
            self.__vec_idx_mgr.delete_vector(idx)

    def remove_files(self, file_paths: list[str]) -> None:
        self.__init_event.wait()
        file_set = {file_ops.fast_normalize(p) for p in file_paths}
        for idx, (index_file, _) in enumerate(self.__name_idx_mgr.name_index):
            if index_file == NameIndexManager.NOTEXISTS:
                continue
            if index_file in file_set:
                self.__name_idx_mgr.delete_name(idx)
                self.__vec_idx_mgr.delete_vector(idx)

    def checkout(
            self,
            content: Image.Image | str, threshold: float = 0.0,
            file_ext_label: str = "",
            size_min: float | None = None,
            size_max: float | None = None,
            folder_filters: list[str] | None = None,
            dedup: bool = False
        ) -> Iterator[tuple[Path, float]]:
        self.__init_event.wait()
        self.__checkout_status = SearchStatus.OK

        if self.__name_idx_mgr.results_count == 0:
            self.__checkout_status = SearchStatus.EMPTY_INDEX
            return
        if isinstance(content, str) and content == "":
            self.__checkout_status = SearchStatus.EMPTY_INPUT
            return

        fv = self.__multimodal_encoder.encode_image(content) if isinstance(content, Image.Image) \
             else self.__multimodal_encoder.encode_text(sub(r"[\s,]+", "，", content))

        if fv is None:
            logging.warning("搜索失败：编码器返回空特征向量，请检查模型文件是否存在")
            self.__checkout_status = SearchStatus.ENCODE_FAILED
            return

        sim_list, ids_list = self.__vec_idx_mgr.match(fv, self.__name_idx_mgr.results_count)
        name_index_len = len(self.__name_idx_mgr.name_index)

        yield from self._filter_and_yield_results(
            ids_list, sim_list, threshold, name_index_len, file_ext_label, 
            size_min, size_max, folder_filters, dedup
        )

    def _filter_and_yield_results(
            self,
            ids_list: list[int], sim_list: list[float],
            threshold: float, name_index_len: int,
            file_ext_label: str,
            size_min: float | None, size_max: float | None,
            folder_filters: list[str] | None,
            dedup: bool = False
        ) -> Iterator[tuple[Path, float]]:
        ext_set = Setting.ext_group_map.get(file_ext_label)
        yielded_count = 0
        threshold -= THRESHOLD_EPSILON
        prev_similarity: float | None = None
        prev_sizes: list[int] = []

        for img_id, similarity in zip(ids_list, sim_list):
            if similarity < threshold:
                break
            if img_id >= name_index_len:
                logging.warning(f"发现孤立向量ID={img_id}，已自动清理")
                self.__vec_idx_mgr.delete_vector(img_id)
                continue

            file_path = Path(self.__name_idx_mgr.name_index[img_id][0])

            if ext_set and file_path.suffix.lower() not in ext_set:
                continue

            try:
                st_size = file_path.stat().st_size
            except OSError:
                self.__checkout_status = SearchStatus.PARTIAL_OMITTED
                continue
            if size_min is not None or size_max is not None:
                file_size_mb = st_size / (1024 * 1024)
                if size_min is not None and file_size_mb < size_min:
                    continue
                if size_max is not None and file_size_mb > size_max:
                    continue

            if folder_filters:
                if not any(file_ops.is_path_under(file_path, f) for f in folder_filters):
                    continue

            if dedup:
                if prev_similarity is None:
                    prev_similarity = similarity
                    prev_sizes = [st_size]
                elif abs(similarity - prev_similarity) < THRESHOLD_EPSILON:
                    if st_size in prev_sizes:
                        prev_sizes.append(st_size)
                        continue
                    prev_sizes.append(st_size)
                else:
                    prev_similarity = similarity
                    prev_sizes = [st_size]

            yielded_count += 1
            yield (file_path, similarity)

        if yielded_count == 0:
            self.__checkout_status = SearchStatus.NO_RESULTS

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

    def rebuild_index(
            self, 
            image_dirs: list[str], 
            max_workers: int, 
            exclude_rules: list[str],
            progress_bar: tqdm
        ) -> None:
        self.__init_event.wait()
        try:
            self.remove_nonexists()
            self.remove_duplicate()
            for image_dir in image_dirs:
                self.remove_files(self.__get_changed_files(image_dir))
                
            if not self.verify_index_match():
                self.reset_index()

            valid_ids = [
                idx for idx, (fpath, _) in enumerate(self.__name_idx_mgr.name_index)
                if fpath != NameIndexManager.NOTEXISTS
            ]
            if not valid_ids:
                self.reset_index()
                return
            try:
                new_mgr = self.__vec_idx_mgr.build_from_vectors(
                    ids=valid_ids, 
                    old_mgr=self.__vec_idx_mgr,
                    progress_bar=progress_bar,
                    stop_check=lambda: self.force_stop_update
                )
                if new_mgr is None:
                    return
                self.__vec_idx_mgr = new_mgr
                self.__name_idx_mgr.compact(valid_ids)
            except Exception as e:
                logging.error(f"软重建失败: {e}", exc_info=True)
                self.reset_index()
        except Exception as e:
            logging.exception(f"重建索引过程异常：{e}，执行硬重建")
            self.reset_index()
        finally:
            self.update_index(image_dirs, max_workers, exclude_rules, progress_bar)
            self.save_index()

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
