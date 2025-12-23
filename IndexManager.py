from pathlib import Path
from typing import Literal, Callable
import json
import logging

import numpy as np
import hnswlib


from utils import FileOperation



class VectorIndexManager:
    def __init__(
            self, 
            index_path: str, 
            index_capacity: int,
            space: Literal["l2", "cosine"],
            dim: int
        ) -> None:
        self.__index_path: str = index_path
        self.__index_capacity: int = index_capacity
        self.__space: Literal["l2", "cosine"] = space
        self.__dim: int = dim
        self.match: Callable = lambda: None
        self.__init_index()
        self.__init_match_function()

    def __init_index(self) -> None:
        self.__hnsw_index = hnswlib.Index(space=self.__space, dim=self.__dim)
        if Path(self.__index_path).exists():
            self.__hnsw_index.load_index(self.__index_path, max_elements=self.__index_capacity)
        else:
            self.__hnsw_index.init_index(max_elements=self.__index_capacity, ef_construction=200, M=32)

    def __init_match_function(self) -> None:
        if self.__space == "cosine":
            self.match = self.match_with_cosine
        elif self.__space == "l2":
            self.match = self.match_with_l2
        else:
            self.match = lambda: None

    def reset_index(self) -> None:
        FileOperation.delete_file(self.__index_path)
        self.__init_index()

    def save_index(self) -> None:
        self.__hnsw_index.save_index(self.__index_path)

    def add_vector(self, fv: np.ndarray, idx: int) -> None:
        self.__hnsw_index.add_items(fv, idx)

    def delete_vector(self, idx: int) -> None:
        try:
            self.__hnsw_index.mark_deleted(idx)
        except Exception as e:
            logging.error(f"删除向量时出错: {e}")

    def match_with_cosine(self, fv, nc=5):
        labels, distances = self.__hnsw_index.knn_query(fv, k=nc)
        cos_similarities = 1.0 - distances[0]
        logits_per_image = 100 * cos_similarities
        return logits_per_image, labels[0]
    
    def match_with_l2(self, fv, nc=5):
        query = self.__hnsw_index.knn_query(fv, k=nc)
        similarity = (1 - np.tanh(query[1][0] / 3000)) * 100
        return similarity, query[0][0]



class NameIndexManager(object):
    NOTEXISTS = 'NOTEXISTS'
    def __init__(self, name_index_path: Path, max_match_count: int) -> None:
        self.__name_index_path = name_index_path
        self.__max_match_count = max_match_count
        self.__init_index()

    @property
    def name_index(self) -> list[list]:
        return self.__name_index
    
    @property
    def results_count(self) -> int:
        return min(self.__max_match_count, self.__valid_index_count)
    
    def update_max_match_count(self, max_match_count: int) -> None:
        self.__max_match_count = max_match_count
   
    def __init_index(self) -> None:
        try:
            with open(self.__name_index_path, "r", encoding="utf-8") as f:
                self.__name_index = json.load(f)
        except json.JSONDecodeError:
            self.__name_index = []
        except FileNotFoundError:
            Path.mkdir(self.__name_index_path.parent, exist_ok=True)
            self.__name_index = []
        finally:
            self.__valid_index_count = sum(
                index_file != NameIndexManager.NOTEXISTS
                for index_file, _ in self.__name_index
            )
    
    def add_name(self, name: Path | str, idx: int) -> None:
        while idx > len(self.__name_index) - 1:
            self.__name_index.append([NameIndexManager.NOTEXISTS, 0])
        self.__name_index[idx] = [str(name), FileOperation.get_metainfo(name)]
        self.__valid_index_count += 1
    
    def delete_name(self, idx: int) -> None:
        try:
            self.__name_index[idx][0] = NameIndexManager.NOTEXISTS
            self.__valid_index_count -= 1
        except IndexError:
            pass

    def reset_index(self) -> None:
        FileOperation.delete_file(self.__name_index_path)
        self.__init_index()

    def save_index(self) -> None:
        with open(self.__name_index_path, 'w', encoding='utf-8') as f:
            json.dump(self.__name_index, f, ensure_ascii=False, indent=4)


