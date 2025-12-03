from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Iterator
import json

import numpy as np
from PIL import Image, UnidentifiedImageError
from tqdm import tqdm
import hnswlib
import onnxruntime


from utils import FileOperation
from setting import Setting






class EfficientIR:
    MEAN_VEC = np.array([0.485, 0.456, 0.406], dtype=np.float32)[:, None, None]
    STDDEV_VEC = np.array([0.229, 0.224, 0.225], dtype=np.float32)[:, None, None]
    SHIFT = -MEAN_VEC / STDDEV_VEC
    SCALE = 1.0 / (255.0 * STDDEV_VEC)

    def __init__(self, img_size, index_capacity, index_path, model_path) -> None:
        self.__img_size = img_size
        self.__index_capacity = index_capacity
        self.__index_path = index_path
        self.__model_path = model_path
        self.__init_index()
        self.__init_model()
        Image.MAX_IMAGE_PIXELS = None

    def __img_preprocess(self, image_path: str | Path) -> None | np.ndarray:
        try:
            img: Image.Image = Image.open(image_path)
            img = img.resize((self.__img_size, self.__img_size), Image.Resampling.BICUBIC).convert('RGB')
        except (OSError, FileNotFoundError, UnidentifiedImageError):
            return None
        img_data = np.asarray(img, dtype=np.float32).transpose(2, 0, 1)
        norm_img_data = img_data * self.SCALE + self.SHIFT
        norm_img_data = np.expand_dims(norm_img_data, axis=0)
        return norm_img_data

    def __init_model(self) -> None:
        self.session_opti = onnxruntime.SessionOptions()
        self.session_opti.enable_mem_pattern = False
        self.session = onnxruntime.InferenceSession(self.__model_path, self.session_opti)
        self.model_input = self.session.get_inputs()[0].name

    def __init_index(self) -> None:
        self.__hnsw_index = hnswlib.Index(space='l2', dim=1000)
        if Path(self.__index_path).exists():
            self.__hnsw_index.load_index(self.__index_path, max_elements=self.__index_capacity)
        else:
            self.__hnsw_index.init_index(max_elements=self.__index_capacity, M=48, ef_construction=200)

    def reset_index(self) -> None:
        FileOperation.delete_file(self.__index_path)
        self.__init_index()

    def save_index(self) -> None:
        self.__hnsw_index.save_index(self.__index_path)

    def get_fv(self, image_path: str | Path) -> np.ndarray | None:
        norm_img_data = self.__img_preprocess(image_path)
        if norm_img_data is None:
            return None
        result = self.session.run([], {self.model_input: norm_img_data})
        return result[0][0]

    def add_fv(self, fv: np.ndarray, idx: int) -> None:
        self.__hnsw_index.add_items(fv, idx)

    def delete_fv(self, idx: int) -> None:
        try:
            self.__hnsw_index.mark_deleted(idx)
        except Exception as e:
            print(f"删除了该索引{idx}")
            pass

    def match(self, fv, nc=5):
        query = self.__hnsw_index.knn_query(fv, k=nc)
        similarity = (1-np.tanh(query[1][0] / 3000))*100
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
            print(self.__valid_index_count)
    
    def add_name(self, name: Path | str, idx: int) -> None:
        while idx > len(self.__name_index) - 1:
            self.__name_index.append([])
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



class SearchTool(object):
    def __init__(self, setting: Setting) -> None:
        self.__ir_engine = EfficientIR(
            setting.get_config_property("img_size"),
            setting.get_config_property("index_capacity"),
            setting.get_config_property("index_path"),
            setting.get_config_property("model_path")
        )
        self.__name_idx_mgr = NameIndexManager(
            Path(setting.get_config_property("name_index_path")),
            setting.get_config_property("max_match_count")
        )

    def __get_changed_files_index(self) -> list[tuple[int, str]]:
        changed_files_index = []
        for idx, [index_file, old_metainfo] in enumerate(self.__name_idx_mgr.name_index):
            if index_file == NameIndexManager.NOTEXISTS:
                continue
            new_metainfo = FileOperation.get_metainfo(index_file)
            if old_metainfo != new_metainfo:
                changed_files_index.append((idx, index_file))
        return changed_files_index
    
    def __get_new_files_index(self, target_dir: str) -> list[tuple[int, str]]:
        new_files_index = []
        current_files = FileOperation.get_file_iterator(target_dir)
        existing_files = set(i[0] for i in self.__name_idx_mgr.name_index)
        new_files = [f for f in current_files if f not in existing_files]

        if not new_files:
            return []

        for idx, [index_file, _] in enumerate(self.__name_idx_mgr.name_index):
            if index_file == NameIndexManager.NOTEXISTS:
                new_files_index.append([idx, new_files.pop()]) 
            if len(new_files) == 0:
                break
        for idx, new_file in enumerate(new_files, len(self.__name_idx_mgr.name_index)):
            new_files_index.append([idx, new_file])

        return new_files_index

    def __index_target_dir(self, target_dir) -> list[tuple[int, str]]:
        changed_files_index = self.__get_changed_files_index()
        new_files_index = self.__get_new_files_index(target_dir)
        return changed_files_index + new_files_index
    
    def update_ir_index(self, image_dir, max_workers: int = 20) -> None:
        def _process_item(item) -> tuple[int, str, np.ndarray | None]:
            idx, fpath = item
            fv = self.__ir_engine.get_fv(fpath)
            return idx, fpath, fv
      
        need_to_update = self.__index_target_dir(image_dir)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            pbar = tqdm(total=len(need_to_update), ascii=False, ncols=50)
            futures = [executor.submit(_process_item, item) for item in need_to_update]
            for future in as_completed(futures):
                idx, fpath, fv = future.result()
                if fv is not None:
                    self.__ir_engine.add_fv(fv, idx)
                    self.__name_idx_mgr.add_name(fpath, idx)
                pbar.update(1)
            pbar.close()
          
    def remove_nonexists(self) -> None:
        for idx, (index_file, _) in tqdm(enumerate(self.__name_idx_mgr.name_index), ascii=False, ncols=50):
            if Path(index_file).exists() or index_file == NameIndexManager.NOTEXISTS:
                continue
            self.__name_idx_mgr.delete_name(idx)
            self.__ir_engine.delete_fv(idx)

    def remove_files_in_directory(self, directory: str) -> None:
        directory_path = Path(directory).resolve()
        for idx, (index_file, _) in enumerate(self.__name_idx_mgr.name_index):
            if index_file == NameIndexManager.NOTEXISTS:
                continue
            file_path = Path(index_file).resolve()
            if not file_path.is_relative_to(directory_path):
                continue
            self.__name_idx_mgr.delete_name(idx)
            self.__ir_engine.delete_fv(idx)

    def checkout(self, image_path) -> Iterator[tuple[float, str]]:
        results_count = self.__name_idx_mgr.results_count
        print(results_count)
        if results_count == 0:
            return
        
        fv = self.__ir_engine.get_fv(image_path)
        if fv is None:
            return
        
        sim_list, ids_list = self.__ir_engine.match(fv, results_count)
        for similarity, img_id in zip(sim_list, ids_list):
            yield (similarity, self.__name_idx_mgr.name_index[img_id][0])

    def reset_index(self) -> None:
        self.__ir_engine.reset_index()
        self.__name_idx_mgr.reset_index()

    def save_index(self) -> None:
        try:
            self.__ir_engine.save_index()
            self.__name_idx_mgr.save_index()
        except Exception:
            pass


