from pathlib import Path

import numpy as np
from PIL import Image, UnidentifiedImageError
import hnswlib
import onnxruntime


class EfficientIR:
    def __init__(self, img_size, index_capacity, index_path, model_path):
        self.MEAN_VEC = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        self.STDDEV_VEC = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        self.img_size = img_size
        self.index_capacity = index_capacity
        self.index_path = index_path
        self.model_path = model_path
        self.init_index()
        self.load_index()
        self.init_model()
        Image.MAX_IMAGE_PIXELS = None

    def img_preprocess(self, image_path):
        try:
            img: Image.Image = Image.open(image_path)
            img = img.resize((self.img_size, self.img_size), Image.Resampling.BICUBIC).convert('RGB')
        except (OSError, UnidentifiedImageError):
            return None
        img_data = np.array(img).transpose(2, 0, 1).astype(np.float32)
        norm_img_data = (img_data / 255.0 - self.MEAN_VEC[:, None, None]) / self.STDDEV_VEC[:, None, None]
        norm_img_data = np.expand_dims(norm_img_data, axis=0)
        return norm_img_data

    def init_index(self):
        self.hnsw_index = hnswlib.Index(space='l2', dim=1000)
        return self.hnsw_index

    def load_index(self):
        if Path(self.index_path).exists():
            self.hnsw_index.load_index(self.index_path, max_elements=self.index_capacity)
        else:
            self.hnsw_index.init_index(max_elements=self.index_capacity, ef_construction=200, M=48)

    def save_index(self):
        self.hnsw_index.save_index(self.index_path)

    def init_model(self):
        self.session_opti = onnxruntime.SessionOptions()
        self.session_opti.enable_mem_pattern = False
        self.session = onnxruntime.InferenceSession(self.model_path, self.session_opti)
        self.model_input = self.session.get_inputs()[0].name
        return self.session, self.model_input

    def get_fv(self, image_path):
        norm_img_data = self.img_preprocess(image_path)
        if norm_img_data is None:
            return None
        result = self.session.run([], {self.model_input: norm_img_data})
        return result[0][0] # type: ignore

    def add_fv(self, fv, idx):
        self.hnsw_index.add_items(fv, idx)

    def match(self, fv, nc=5):
        query = self.hnsw_index.knn_query(fv, k=nc)
        similarity = (1-np.tanh(query[1][0]/3000))*100
        return similarity, query[0][0]

