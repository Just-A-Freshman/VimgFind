from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Thread, Event
from pathlib import Path
from typing import Iterator, Literal
from collections import defaultdict
from re import split


import numpy as np
from tqdm import tqdm

from setting import Setting
from IndexManager import VectorIndexManager, NameIndexManager
from encoder import MultiModalEncoder
from utils import FileOperation



class SearchTool(object):
    def __init__(self, setting: Setting) -> None:
        self.__search_event = Event()
        self.__search_event.set()
        self.__init_event = Event()
        Thread(target=self.__async_init, args=(setting, ), daemon=True).start()
        
    def __async_init(self, setting: Setting) -> None:
        self.__vec_idx_mgr = VectorIndexManager(
            setting.get_config("index", "vector_index_path"),
            setting.get_config("index", "index_capacity"),
            setting.get_config("index", "index_dim")
        )
        self.__name_idx_mgr = NameIndexManager(
            Path(setting.get_config("index", "name_index_path")),
            setting.get_config("index", "max_match_count")
        )
        self.__multimodal_encoder = MultiModalEncoder(
            Path(setting.get_config("model", "vocab_path")),
            Path(setting.get_config("model", "image_encoder_path")),
            Path(setting.get_config("model", "text_encoder_path")),
            np.array(setting.get_config("model", "mean"), dtype=np.float32)[:, None, None],
            np.array(setting.get_config("model", "std"), dtype=np.float32)[:, None, None],
            setting.get_config("model", "image_size"),
            setting.get_config("model", "context_length")
        )
        self.__init_event.set()

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
    
    def update_ir_index(self, image_dir, max_workers: int = 10) -> None:
        def _process_item(item) -> tuple[int, str, np.ndarray | None]:
            self.__search_event.wait()
            idx, fpath = item
            fv = self.__multimodal_encoder.encode_image(fpath)
            return idx, fpath, fv
        self.__init_event.wait()
        need_to_update = self.__index_target_dir(image_dir)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            pbar = tqdm(total=len(need_to_update), ascii=False, ncols=50)
            futures = [executor.submit(_process_item, item) for item in need_to_update]
            for future in as_completed(futures):
                idx, fpath, fv = future.result()
                if fv is not None:
                    self.__vec_idx_mgr.add_vector(fv, idx)
                    self.__name_idx_mgr.add_name(fpath, idx)
                pbar.update(1)
            pbar.close()
          
    def remove_nonexists(self) -> None:
        self.__init_event.wait()
        for idx, (index_file, _) in tqdm(enumerate(self.__name_idx_mgr.name_index), ascii=False, ncols=50):
            if Path(index_file).exists() or index_file == NameIndexManager.NOTEXISTS:
                continue
            self.__name_idx_mgr.delete_name(idx)
            self.__vec_idx_mgr.delete_vector(idx)

    def remove_files_in_directory(self, directory: str) -> None:
        self.__init_event.wait()
        directory_path = Path(directory).resolve()
        for idx, (index_file, _) in enumerate(self.__name_idx_mgr.name_index):
            if index_file == NameIndexManager.NOTEXISTS:
                continue
            file_path = Path(index_file).resolve()
            if not file_path.is_relative_to(directory_path):
                continue
            self.__name_idx_mgr.delete_name(idx)
            self.__vec_idx_mgr.delete_vector(idx)

    def checkout(self, content: str, input_type: Literal["image", "text"]) -> Iterator[tuple[float, str]]:
        self.__init_event.wait()
        results_count = self.__name_idx_mgr.results_count
        if results_count == 0 or content.strip() == "":
            return
        self.stop_update_index()
        if input_type == "image":
            fv = self.__multimodal_encoder.encode_image(content)
        else:
            keywords = split(r"[\s|,]", content)
            if len(keywords) > 1:
                combine_sentence = f"一张照片同时包含了{'、'.join(keywords[:-2])}和{keywords[-1]}"
            else:
                combine_sentence = content
            fv = self.__multimodal_encoder.encode_text(combine_sentence)
            
        if fv is None:
            return
        sim_list, ids_list = self.__vec_idx_mgr.match(fv, results_count)
        for similarity, img_id in zip(sim_list, ids_list):
            yield (similarity, self.__name_idx_mgr.name_index[img_id][0])
        self.continue_update_index()

    def reset_index(self) -> None:
        self.__init_event.wait()
        self.__vec_idx_mgr.reset_index()
        self.__name_idx_mgr.reset_index()

    def save_index(self) -> None:
        self.__init_event.wait()
        try:
            self.__vec_idx_mgr.save_index()
            self.__name_idx_mgr.save_index()
        except Exception:
            pass

    def stop_update_index(self) -> None:
        self.__search_event.clear()

    def continue_update_index(self) -> None:
        self.__search_event.set()

