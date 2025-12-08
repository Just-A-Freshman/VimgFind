from pathlib import Path


from PIL import Image
import numpy as np
import onnxruntime as ort



class MultiModalEncoder:
    def __init__(
            self, 
            image_encoder_path: Path, 
            mean: np.ndarray,
            std: np.ndarray,
            image_size: int
        ) -> None:

        self.__image_encoder_path = image_encoder_path
        self.__image_size = image_size
        self.__mean = mean
        self.__std = std
        self.image_session = self._init_onnx_session(self.__image_encoder_path)

    def _init_onnx_session(self, model_path) -> ort.InferenceSession:
        try:
            providers = ['CPUExecutionProvider']
            session = ort.InferenceSession(
                str(model_path),
                providers=providers
            )
            return session
        except Exception as e:
            raise RuntimeError(f"加载ONNX模型失败 {model_path}: {e}")

    def _preprocess_image(self, img: Image.Image) -> np.ndarray | None:
        img = img.convert("RGB")
        img = img.resize((self.__image_size, self.__image_size), Image.Resampling.BICUBIC)
        img_array = np.asarray(img, dtype=np.float32).transpose(2, 0, 1)
        img_array = (img_array / 255.0 - self.__mean) / self.__std
        img_array = np.expand_dims(img_array, axis=0)
        return img_array

    def encode_image(self, image_obj: Image.Image) -> np.ndarray | None:
        processed_image = self._preprocess_image(image_obj)
        if processed_image is None:
            return None
    
        input_name = self.image_session.get_inputs()[0].name
        result = self.image_session.run([], {input_name: processed_image})

        image_features = result[0][0]
        return image_features

