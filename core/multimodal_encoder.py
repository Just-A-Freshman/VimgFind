from pathlib import Path
import logging
from typing import Callable, Literal

from .tokenizer import FullTokenizer
from PIL import Image
import numpy as np
import onnxruntime as ort



class ImagePreprocess:
    VALID_TYPES = frozenset({"resize", "resize_crop", "resize_pad"})

    def __init__(
        self,
        image_size: int,
        preprocess_type: Literal["resize", "resize_crop", "resize_pad"] = "resize_crop",
        mean: tuple[float, float, float] | np.ndarray | None = None,
        std: tuple[float, float, float] | np.ndarray | None = None,
        fill_color: tuple[int, int, int] | None = None,
    ) -> None:
        if preprocess_type not in self.VALID_TYPES:
            raise ValueError(f"未知的 preprocess_type: {preprocess_type!r}")

        self.__image_size = image_size
        self.__mean = np.array(mean, dtype=np.float32).ravel()[:, None, None] if mean is not None else None
        self.__std = np.array(std, dtype=np.float32).ravel()[:, None, None] if std is not None else None

        if fill_color is not None:
            self.__fill_color = fill_color
        elif self.__mean is not None:
            self.__fill_color = tuple(
                max(0, min(255, int(round(float(m) * 255))))
                for m in self.__mean.ravel().tolist()
            )
        else:
            self.__fill_color = (0, 0, 0)

        _geo_map: dict[str, Callable[[Image.Image], Image.Image]] = {
            "resize": self.__apply_resize,
            "resize_crop": self.__apply_resize_crop,
            "resize_pad": self.__apply_resize_pad,
        }
        self.__apply_geometry = _geo_map[preprocess_type]

    def __call__(self, img: Image.Image) -> np.ndarray:
        img = self._ensure_rgb(img)
        img = self.__apply_geometry(img)
        arr = np.asarray(img, dtype=np.float32).transpose(2, 0, 1)
        if self.__mean is not None and self.__std is not None:
            arr = (arr / 255.0 - self.__mean) / self.__std
        return np.expand_dims(arr, axis=0)

    @staticmethod
    def _ensure_rgb(img: Image.Image) -> Image.Image:
        if img.mode in ('P', 'PA', '1', 'L', 'LA'):
            img = img.convert('RGBA')
        if img.mode == 'RGBA':
            background = Image.new('RGB', img.size)
            background.paste(img, mask=img.split()[-1])
            img = background
        else:
            img = img.convert("RGB")
        return img

    def __apply_resize(self, img: Image.Image) -> Image.Image:
        return img.resize((self.__image_size, self.__image_size), Image.Resampling.BICUBIC)

    def __apply_resize_crop(self, img: Image.Image) -> Image.Image:
        w, h = img.size
        if w < h:
            new_w = self.__image_size
            new_h = int(h * self.__image_size / w)
        else:
            new_h = self.__image_size
            new_w = int(w * self.__image_size / h)
        img = img.resize((new_w, new_h), Image.Resampling.BICUBIC)
        left = (new_w - self.__image_size) // 2
        top = (new_h - self.__image_size) // 2
        return img.crop((left, top, left + self.__image_size, top + self.__image_size))

    def __apply_resize_pad(self, img: Image.Image) -> Image.Image:
        w, h = img.size
        scale = self.__image_size / max(w, h)
        new_w = int(round(w * scale))
        new_h = int(round(h * scale))
        img = img.resize((new_w, new_h), Image.Resampling.BICUBIC)
        canvas = Image.new("RGB", (self.__image_size, self.__image_size), self.__fill_color)   # type:ignore
        left = (self.__image_size - new_w) // 2
        top = (self.__image_size - new_h) // 2
        canvas.paste(img, (left, top))
        return canvas


class MultiModalEncoder:
    def __init__(
            self,
            vocab_path: Path | None,
            image_encoder_path: Path | None,
            text_encoder_path: Path | None,
            preprocess: ImagePreprocess,
            normalization: bool,
            context_length: int
        ) -> None:

        self.__preprocess = preprocess
        self.__normalization = normalization
        self.__context_length = context_length
        self.__tokenizer = FullTokenizer(vocab_path) if vocab_path else None
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

    def _init_onnx_session(self, model_path: Path | None) -> ort.InferenceSession | None:
        if model_path is None:
            return None
        try:
            session = ort.InferenceSession(
                str(model_path),
                providers=['CPUExecutionProvider'],
                provider_options=[{'intra_op_num_threads': 1, 'inter_op_num_threads': 1}]
            )
            return session
        except Exception as e:
            logging.error(f"加载ONNX模型[{model_path}]失败: {e}")
            return None

    def _normalization(self, fv: np.ndarray) -> None:
        if self.__normalization:
            norm = np.linalg.norm(fv, axis=-1, keepdims=True)
            norm[norm == 0] = 1.0
            fv /= norm

    def encode_image(self, image_obj: Image.Image) -> np.ndarray | None:
        assert self.image_session is not None, "该模型不是图片模型，无法进行以图搜图"
        processed_image = self.__preprocess(image_obj)
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
        assert self.text_session is not None and self.__tokenizer is not None, "该模型不是文字模型，无法进行以文搜图" 
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
            return None

    def close(self) -> None:
        self.image_session = None
        self.text_session = None
        self.__tokenizer = None

