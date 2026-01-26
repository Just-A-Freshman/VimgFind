from pathlib import Path
import logging


from tokenizer import FullTokenizer
from PIL import Image
import numpy as np
import onnxruntime as ort



class MultiModalEncoder:
    def __init__(
            self, 
            vocab_path: Path, 
            image_encoder_path: Path, 
            text_encoder_path: Path, 
            mean: np.ndarray,
            std: np.ndarray,
            normalization: bool,
            image_size: int,
            context_length: int
        ) -> None:

        self.__image_size = image_size
        self.__mean = mean
        self.__std = std
        self.__normalization = normalization
        self.__context_length = context_length
        self.__tokenizer = FullTokenizer(vocab_path) if vocab_path.exists() else None
        self.image_session = self._init_onnx_session(image_encoder_path)
        self.text_session = self._init_onnx_session(text_encoder_path)

    def tokenize(self, texts) -> np.ndarray:
        if self.__tokenizer is None:
            return np.ndarray([])
        if isinstance(texts, str):
            texts = [texts]

        all_tokens = []
        for text in texts:
            all_tokens.append(
                [self.__tokenizer.vocab['[CLS]']] +
                self.__tokenizer.convert_tokens_to_ids(
                    self.__tokenizer.tokenize(text)
                )[:self.__context_length - 2] + 
                [self.__tokenizer.vocab['[SEP]']]
            )

        result = np.zeros((len(all_tokens), self.__context_length), dtype=np.int64)
        for i, tokens in enumerate(all_tokens):
            assert len(tokens) <= self.__context_length
            result[i, :len(tokens)] = tokens
        return result

    def _init_onnx_session(self, model_path) -> ort.InferenceSession | None:
        try:
            session = ort.InferenceSession(
                str(model_path),
                providers=['CPUExecutionProvider'],
                provider_options=[{'intra_op_num_threads': 1, 'inter_op_num_threads': 1}]
            )
            return session
        except Exception as e:
            logging.error(f"加载ONNX模型失败 {model_path}: {e}")
            return None

    def _normalization(self, fv: np.ndarray) -> None:
        if self.__normalization:
            norm = np.linalg.norm(fv, axis=-1, keepdims=True)
            fv[fv == 0] = 1.0
            fv /= norm

    def _preprocess_image(self, img: Image.Image) -> np.ndarray | None:
        # img = img.convert("RGB")
        if img.mode in ('P', 'PA', '1', 'L', 'LA'):
            img = img.convert('RGBA')
        
        if img.mode == 'RGBA':
            # 如果有透明通道，创建白色背景
            background = Image.new('RGB', img.size)
            background.paste(img, mask=img.split()[-1])  # 使用alpha通道作为mask
            img = background
        else:
            img = img.convert("RGB")
        img = img.resize((self.__image_size, self.__image_size), Image.Resampling.BICUBIC)
        img_array = np.asarray(img, dtype=np.float32).transpose(2, 0, 1)
        img_array = (img_array / 255.0 - self.__mean) / self.__std
        img_array = np.expand_dims(img_array, axis=0)
        return img_array

    def encode_image(self, image_obj: Image.Image) -> np.ndarray | None:
        if self.image_session is None:
            return None
        
        processed_image = self._preprocess_image(image_obj)
        if processed_image is None:
            return None
        try:
            input_name = self.image_session.get_inputs()[0].name
            result = self.image_session.run([], {input_name: processed_image})
            image_features = result[0][0]
            self._normalization(image_features)
        except Exception as e:
            logging.error(f"编码图像时出现错误: {e}")
            return None
        return image_features
    
    def encode_text(self, input_text: str) -> np.ndarray | None:
        if self.text_session is None or self.__tokenizer is None:
            return None
        try:
            text = self.tokenize(input_text)
            text_features_list = []
            for i in range(len(text)):
                one_text = np.expand_dims(text[i], axis=0)
                text_feature = self.text_session.run([], {self.text_session.get_inputs()[0].name: one_text})[0].squeeze()
                text_features_list.append(text_feature)
            text_features = np.stack(text_features_list, axis=0)
            self._normalization(text_features)
            return text_features
        except Exception as e:
            logging.error(f"编码文字时出现错误: {e}")

