from pathlib import Path
import json
import logging

import numpy as np
import hnswlib

import utils.file_ops as file_ops


HNSW_EF_CONSTRUCTION = 200
HNSW_M = 32
HNSW_MIN_EF = 100
INITIAL_CAPCITY = 50000


class VectorIndexManager:
    __slots__ = ("__index_path", "__index_capacity", "__dim", "__current_max_elements", "__hnsw_index")

    def __init__(
            self,
            index_path: str,
            index_capacity: int,
            dim: int,
            current_max_elements: int
        ) -> None:
        self.__index_path: str = index_path
        self.__index_capacity: int = index_capacity
        self.__dim: int = dim
        self.__current_max_elements: int = current_max_elements
        self.__hnsw_index: hnswlib.Index | None = None
        self.__init_index()

    def __init_index(self) -> None:
        self.__hnsw_index = hnswlib.Index(space="cosine", dim=self.__dim)
        if Path(self.__index_path).exists():
            current_max_element = min(max(self.__current_max_elements * 2, INITIAL_CAPCITY), self.__index_capacity)
            self.__hnsw_index.load_index(self.__index_path, max_elements=current_max_element)
            self.__current_max_elements = current_max_element
        else:
            self.__hnsw_index.init_index(
                max_elements=INITIAL_CAPCITY,
                ef_construction=HNSW_EF_CONSTRUCTION,
                M=HNSW_M,
                random_seed=42
            )
            self.__current_max_elements = INITIAL_CAPCITY

    def _ensure_capacity(self, needed: int) -> None:
        assert self.__hnsw_index is not None
        if needed < self.__current_max_elements * 0.9:
            return
        new_cap = min(self.__current_max_elements * 2, self.__index_capacity)
        if new_cap > self.__current_max_elements:
            self.__hnsw_index.resize_index(new_cap)
            self.__current_max_elements = new_cap

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
    
    def close(self):
        self.__hnsw_index = None


class NameIndexManager(object):
    NOTEXISTS = 'NOTEXISTS'
    __slots__ = ("__name_index_path", "__max_match_count", "__name_index", "__valid_index_count")

    def __init__(self, name_index_path: str, max_match_count: int) -> None:
        self.__name_index_path = name_index_path
        self.__max_match_count = max_match_count
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
            self.__valid_index_count = sum(
                index_file != NameIndexManager.NOTEXISTS
                for index_file, _ in self.__name_index
            )

    def add_name(self, name: Path | str, idx: int) -> None:
        while idx > len(self.__name_index) - 1:
            self.__name_index.append([NameIndexManager.NOTEXISTS, 0])
        self.__name_index[idx] = [
            file_ops.normalize_path(str(name)),
            file_ops.get_metainfo(name)
        ] 
        self.__valid_index_count += 1

    def delete_name(self, idx: int) -> None:
        try:
            self.__name_index[idx][0] = NameIndexManager.NOTEXISTS
            self.__valid_index_count -= 1
        except IndexError:
            pass

    def reset_index(self) -> None:
        file_ops.delete_file(self.__name_index_path)
        self.__init_index()

    def save_index(self) -> None:
        with open(self.__name_index_path, 'w', encoding='utf-8') as f:
            json.dump(self.__name_index, f, ensure_ascii=False, indent=4)
