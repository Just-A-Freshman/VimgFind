from __future__ import annotations

from pathlib import Path
from typing import Callable
import json
import logging
import os
import tempfile

from tqdm import tqdm
import hnswlib
import numpy as np

import utils.file_ops as file_ops


HNSW_EF_CONSTRUCTION = 200
HNSW_M = 32
HNSW_MIN_EF = 100
INITIAL_CAPCITY = 50000
BATCH_SIZE = 100


class VectorIndexManager:
    __slots__ = ("__index_path", "__index_capacity", "__dim", "__current_capacity", "__hnsw_index")

    def __init__(
            self,
            index_path: str,
            index_capacity: int,
            dim: int,
            current_capacity: int
        ) -> None:
        self.__index_path: str = index_path
        self.__index_capacity: int = index_capacity
        self.__dim: int = dim
        self.__current_capacity: int = current_capacity
        self.__hnsw_index: hnswlib.Index | None = None
        self.__init_index()

    def __init_index(self) -> None:
        self.__hnsw_index = hnswlib.Index(space="cosine", dim=self.__dim)
        if Path(self.__index_path).exists():
            current_capacity = min(max(self.__current_capacity * 2, INITIAL_CAPCITY), self.__index_capacity)
            self.__hnsw_index.load_index(self.__index_path, max_elements=current_capacity)
            self.__current_capacity = current_capacity
        else:
            self.__hnsw_index.init_index(
                max_elements=INITIAL_CAPCITY,
                ef_construction=HNSW_EF_CONSTRUCTION,
                M=HNSW_M,
                random_seed=42
            )
            self.__current_capacity = INITIAL_CAPCITY

    def _ensure_capacity(self, needed: int) -> None:
        assert self.__hnsw_index is not None
        if needed < self.__current_capacity - BATCH_SIZE:
            return
        new_cap = min(self.__current_capacity * 2, self.__index_capacity)
        if new_cap > self.__current_capacity:
            self.__hnsw_index.resize_index(new_cap)
            self.__current_capacity = new_cap

    def reset_index(self) -> None:
        file_ops.delete_file(self.__index_path)
        self.close()
        self.__init_index()

    def save_index(self) -> None:
        assert self.__hnsw_index is not None
        self.__hnsw_index.save_index(self.__index_path)

    def add_vector(self, fv: np.ndarray, idx: int) -> None:
        assert self.__hnsw_index is not None
        self._ensure_capacity(self.__hnsw_index.element_count + 1)
        self.__hnsw_index.add_items(fv, idx)

    def delete_vector(self, idx: int) -> None:
        try:
            assert self.__hnsw_index is not None
            self.__hnsw_index.mark_deleted(idx)
        except Exception as e:
            logging.error(f"删除向量时出错: {e}")

    def match(self, fv, nc=5):
        assert self.__hnsw_index is not None
        self.__hnsw_index.set_ef(max(HNSW_MIN_EF, nc * 2))
        labels, distances = self.__hnsw_index.knn_query(fv, k=nc)
        cos_similarities = 1.0 - distances[0]
        logits_per_image = 100 * cos_similarities
        return logits_per_image, labels[0]
    
    def get_items(self, ids: list[int]) -> np.ndarray:
        assert self.__hnsw_index is not None
        return self.__hnsw_index.get_items(ids)   # type: ignore[return-value]

    @classmethod
    def build_from_vectors(
        cls,
        dim: int,
        ids: list[int],
        old_mgr: "VectorIndexManager",
        index_path: str,
        index_capacity: int,
        progress_bar: tqdm,
        stop_check: None | Callable = None
    ) -> "VectorIndexManager | None":
        total = len(ids)
        progress_bar.total += total
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".npy")
        try:
            with os.fdopen(tmp_fd, "wb") as f:
                for i in range(0, total, BATCH_SIZE):
                    if stop_check and stop_check():
                        return None
                    batch_ids = ids[i:i + BATCH_SIZE]
                    batch_vecs = old_mgr.get_items(batch_ids)
                    f.write(batch_vecs.astype(np.float32).tobytes())

            new_hnsw = hnswlib.Index(space="cosine", dim=dim)
            new_hnsw.init_index(
                max_elements=max(total, INITIAL_CAPCITY),
                ef_construction=HNSW_EF_CONSTRUCTION,
                M=HNSW_M,
                random_seed=42,
            )
            with open(tmp_path, "rb") as f:
                for i in range(0, total, BATCH_SIZE):
                    if stop_check and stop_check():
                        return
                    count = min(BATCH_SIZE, total - i)
                    raw = f.read(count * dim * 4)
                    batch_vecs = np.frombuffer(raw, dtype=np.float32).reshape(count, dim)
                    new_hnsw.add_items(batch_vecs, np.arange(i, i + count))
                    progress_bar.update(count)
                    progress_bar.refresh()
            old_mgr.close()
            new_hnsw.save_index(index_path)
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        return cls(index_path, index_capacity, dim, total)

    def close(self) -> None:
        self.__hnsw_index = None


class NameIndexManager:
    NOTEXISTS = 'NOTEXISTS'
    __slots__ = ("__name_index_path", "__max_match_count", "__name_index", "__valid_index_count")

    def __init__(self, name_index_path: str, max_match_count: int) -> None:
        self.__name_index_path: str = name_index_path
        self.__max_match_count: int = max_match_count
        self.__valid_index_count: int = 0
        self.__init_index()

    @property
    def name_index(self) -> list[list]:
        return self.__name_index

    @property
    def results_count(self) -> int:
        return min(self.__max_match_count, self.__valid_index_count)

    @property
    def valid_index_count(self) -> int:
        return self.__valid_index_count

    def update_max_match_count(self, max_match_count: int) -> None:
        self.__max_match_count = max_match_count

    def __init_index(self) -> None:
        try:
            with open(self.__name_index_path, "r", encoding="utf-8") as f:
                self.__name_index = json.load(f)
        except json.JSONDecodeError:
            self.__name_index = []
        except FileNotFoundError:
            Path(self.__name_index_path).parent.mkdir(exist_ok=True, parents=True)
            self.__name_index = []
        finally:
            for entry in self.__name_index:
                if entry[0] != NameIndexManager.NOTEXISTS:
                    entry[0] = file_ops.fast_normalize(entry[0])
                    self.__valid_index_count += 1

    def add_name(self, name: Path | str) -> int:
        self.__name_index.append([
            file_ops.fast_normalize(str(name)),
            file_ops.get_metainfo(name)
        ])
        self.__valid_index_count += 1
        return len(self.__name_index) - 1

    def delete_name(self, idx: int) -> None:
        try:
            self.__valid_index_count -= self.__name_index[idx][0] != NameIndexManager.NOTEXISTS
            self.__name_index[idx] = [NameIndexManager.NOTEXISTS, 0]
        except IndexError:
            pass

    def compact(self, valid_ids: list[int]) -> None:
        new_index = [self.__name_index[i] for i in valid_ids]
        self.__name_index = new_index
        self.__valid_index_count = len(new_index)

    def reset_index(self) -> None:
        file_ops.delete_file(self.__name_index_path)
        self.__init_index()

    def save_index(self) -> None:
        with open(self.__name_index_path, 'w', encoding='utf-8') as f:
            json.dump(self.__name_index, f, ensure_ascii=False)
