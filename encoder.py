from pathlib import Path


from tokenizer import FullTokenizer
from PIL import Image, UnidentifiedImageError
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
            image_size: int,
            context_length: int
        ) -> None:

        self.__tokenizer = FullTokenizer(vocab_path)
        self.__image_encoder_path = image_encoder_path
        self.__text_encoder_path = text_encoder_path
        self.__image_size = image_size
        self.__mean = mean
        self.__std = std
        self.__context_length = context_length

        self.image_session = self._init_onnx_session(self.__image_encoder_path)
        self.text_session = self._init_onnx_session(self.__text_encoder_path)

    def tokenize(self, texts) -> np.ndarray:
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

    def _preprocess_image(self, image_path: str | Path) -> np.ndarray | None:
        try:
            img = Image.open(image_path).convert('RGB')
        except (OSError, FileNotFoundError, UnidentifiedImageError) as e:
            return None
        img = img.resize((self.__image_size, self.__image_size), Image.Resampling.BICUBIC)
        img_array = np.asarray(img, dtype=np.float32).transpose(2, 0, 1)
        img_array = (img_array / 255.0 - self.__mean) / self.__std
        # img_array = np.asarray(img, dtype=np.float32).transpose(2, 0, 1)
        img_array = np.expand_dims(img_array, axis=0)
        return img_array

    def encode_image(self, image_path: str | Path) -> np.ndarray | None:
        processed_image = self._preprocess_image(image_path)
        if processed_image is None:
            return None
    
        input_name = self.image_session.get_inputs()[0].name
        result = self.image_session.run(None, {input_name: processed_image})

        image_features = result[0][0]
        img_norm = np.linalg.norm(image_features, axis=-1, keepdims=True)
        if img_norm > 0:
            image_features = image_features / img_norm
        
        return image_features
    
    def encode_text(self, input_text: str) -> np.ndarray:
        text = self.tokenize(input_text) 
        text_features = []
        for i in range(len(text)):
            one_text = np.expand_dims(text[i], axis=0)
            text_feature = self.text_session.run(None, {self.text_session.get_inputs()[0].name: one_text})[0].squeeze()
            text_features.append(text_feature)
        text_features = np.stack(text_features, axis=0)
        txt_norm = np.linalg.norm(text_features, axis=1, keepdims=True)
        text_features /= txt_norm
        return text_features

