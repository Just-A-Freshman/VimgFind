from __future__ import annotations

import math
from typing import Callable, Literal
from threading import Lock
import logging

from PIL import Image
import numpy as np
import onnxruntime as ort

from .tokenizer import create_tokenizer
from config.types import EncoderConfig

class ImagePreprocess:
    __slots__ = ("__image_size", "__mean", "__std", "__fill_color", "__ar_params", "__apply_geometry")

    def __init__(
        self,
        image_size: int,
        preprocess_type: Literal["resize", "resize_crop", "resize_pad", "resize_ar"] = "resize_crop",
        mean: tuple[float, float, float] | np.ndarray | None = None,
        std: tuple[float, float, float] | np.ndarray | None = None,
        fill_color: tuple[int, int, int] | None = None,
        patch_size: int = 16,
        pool_size: int = 3,
        max_soft_tokens: int = 0
    ) -> None:
        if preprocess_type not in {"resize", "resize_crop", "resize_pad", "resize_ar"}:
            raise ValueError(f"未知的 preprocess_type: {preprocess_type!r}")
        if preprocess_type == "resize_ar" and min(patch_size, pool_size, max_soft_tokens) <= 0:
            raise ValueError("resize_ar 需要 patch_size / pool_size / max_soft_tokens 均 > 0")

        self.__image_size = image_size
        self.__ar_params = (patch_size, pool_size, max_soft_tokens)
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
            "resize_ar": self.__apply_resize_ar,
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
        canvas = Image.new("RGB", (self.__image_size, self.__image_size), self.__fill_color)   # type: ignore[arg-type]
        left = (self.__image_size - new_w) // 2
        top = (self.__image_size - new_h) // 2
        canvas.paste(img, (left, top))
        return canvas

    def __apply_resize_ar(self, img: Image.Image) -> Image.Image:   
        width, height = img.size
        patch_size, pool_size, max_soft_tokens = self.__ar_params
        side = patch_size * pool_size
        max_patches = max_soft_tokens * pool_size**2
        factor = math.sqrt(max_patches * patch_size**2 / (height * width))
        target_h = int(math.floor(factor * height / side)) * side
        target_w = int(math.floor(factor * width / side)) * side
        max_side = (max_patches // pool_size**2) * side
        if target_h == 0 and target_w == 0:
            raise ValueError(f"{width}x{height} 太小，无法缩放到 {side} 的整数倍")
        if target_h == 0:
            target_h = side
            target_w = min(int(math.floor(width / height)) * side, max_side)
        elif target_w == 0:
            target_w = side
            target_h = min(int(math.floor(height / width)) * side, max_side)

        if target_h * target_w > max_patches * patch_size**2:
            raise ValueError(
                f"{width}x{height} 缩放为 {target_h}x{target_w} 超出 {max_patches} 个 patch 的预算"
            )
        if (target_h, target_w) == (height, width):
            return img
        return img.resize((target_w, target_h), Image.Resampling.BICUBIC)


class MultiModalEncoder:
    __slots__ = (
        "__preprocess", "__normalization", "__output_index",
        "__context_length", "__tokenizer", "__text_encoder_path",
        "__image_encoder_path", "__lock", "__inflight",
        "__image_session", "__text_session"
    )

    def __init__(self, config: EncoderConfig) -> None:
        self.__preprocess = ImagePreprocess(
            image_size=config.image_size,
            preprocess_type=config.preprocess_type,
            mean=config.mean,
            std=config.std,
            fill_color=config.fill_color,
            patch_size=config.patch_size,
            pool_size=config.pool_size,
            max_soft_tokens=config.max_soft_tokens,
        )
        self.__normalization = config.normalization
        self.__output_index = config.output_index
        self.__context_length = config.context_length
        self.__text_encoder_path = config.text_encoder_path
        self.__image_encoder_path = config.image_encoder_path
        self.__image_session = self._init_onnx_session(self.__image_encoder_path)
        self.__tokenizer = None
        self.__text_session = None
        self.__lock = Lock()
        self.__inflight = 0

    def tokenize(self, texts) -> np.ndarray:
        if self.__tokenizer is None:
            return np.ndarray([])
        if isinstance(texts, str):
            texts = [texts]

        bos = getattr(self.__tokenizer, "bos_token_id", None)
        eos = getattr(self.__tokenizer, "eos_token_id", None)
        pad = getattr(self.__tokenizer, "pad_token_id", 0)
        max_len = self.__context_length
        reserve = (1 if bos is not None else 0) + (1 if eos is not None else 0)

        all_tokens = []
        for text in texts:
            ids = self.__tokenizer.encode(text)
            ids = ids[:max_len - reserve]
            if bos is not None:
                ids = [bos] + ids
            if eos is not None:
                ids.append(eos)
            all_tokens.append(ids)

        result = np.full((len(all_tokens), max_len), pad, dtype=np.int64)
        for i, tokens in enumerate(all_tokens):
            result[i, :len(tokens)] = tokens
        return result

    def _init_onnx_session(self, model_path: str | None) -> ort.InferenceSession | None:
        if model_path is None:
            return None
        try:
            session = ort.InferenceSession(
                model_path,
                providers=[('CPUExecutionProvider', {
                    'arena_extend_strategy': 'kSameAsRequested',
                    'enable_cpu_mem_arena': False,
                    'intra_op_num_threads': 1, 
                    'inter_op_num_threads': 1
                })]
            )
            return session
        except Exception as e:
            logging.error(f"加载ONNX模型[{model_path}]失败: {e}")
            return None

    def _normalize(self, fv: np.ndarray) -> None:
        if self.__normalization:
            norm = np.linalg.norm(fv, axis=-1, keepdims=True)
            norm[norm == 0] = 1.0
            fv /= norm

    def encode_image(self, image_obj: Image.Image) -> np.ndarray | None:
        with self.__lock:
            if self.__image_session is None:
                self.__image_session = self._init_onnx_session(self.__image_encoder_path)
        session = self.__image_session
        if session is None:
            logging.error("图像模型未加载，无法进行以图搜图")
            return None
        processed_image = self.__preprocess(image_obj)
        if processed_image is None:
            return None
        with self.__lock:
            self.__inflight += 1
        try:
            input_name = session.get_inputs()[0].name
            result = session.run([], {input_name: processed_image})
            image_features = result[self.__output_index][0] # type: ignore[index]
            self._normalize(image_features)
        except Exception as e:
            logging.error(f"编码图像时出现错误: {e}")
            return None
        finally:
            with self.__lock:
                self.__inflight -= 1
        return image_features

    def encode_text(self, input_text: str) -> np.ndarray | None:
        with self.__lock:
            if self.__text_session is None and self.__text_encoder_path:
                self.__text_session = self._init_onnx_session(self.__text_encoder_path)
                self.__tokenizer = create_tokenizer(".")
        
        assert self.__text_session and self.__tokenizer, "该模型不是文本模型，\n无法进行以文搜图"
        with self.__lock:
            self.__inflight += 1
        try:
            text = self.tokenize(input_text)
            attention_mask = (text != self.__tokenizer.pad_token_id).astype(np.int32)
            text_features_list = []
            for i in range(len(text)):
                one_text = np.expand_dims(text[i], axis=0)
                one_mask = np.expand_dims(attention_mask[i], axis=0)
                feed = {}
                for inp in self.__text_session.get_inputs():
                    name = inp.name.lower()
                    if "attention_mask" in name:
                        dtype = np.int32 if "int32" in inp.type else np.int64
                        feed[inp.name] = one_mask.astype(dtype)
                    elif "input_ids" in name:
                        dtype = np.int32 if "int32" in inp.type else np.int64
                        feed[inp.name] = one_text.astype(dtype)
                    else:
                        feed[inp.name] = one_text

                results = self.__text_session.run(None, feed)
                text_feature = None
                for r in results:
                    if isinstance(r, np.ndarray) and len(r.shape) == 2:
                        text_feature = r.squeeze()
                        break
                if text_feature is None:
                    if isinstance(results[0], np.ndarray):
                        text_feature = results[0].squeeze()
                    else:
                        raise TypeError("Unexpected sparse output from ONNX model")
                text_features_list.append(text_feature)

            text_features = np.stack(text_features_list, axis=0)
            self._normalize(text_features)
            return text_features
        except Exception as e:
            logging.error(f"编码文字时出现错误: {e}")
            return None
        finally:
            with self.__lock:
                self.__inflight -= 1
        
    def clear_cache(self):
        if self.__image_session is not None:
            self.__image_session.set_providers(
                providers=['CPUExecutionProvider'],
                provider_options=[{
                    'enable_cpu_mem_arena': False,
                    'intra_op_num_threads': 1,
                    'inter_op_num_threads': 1
                }]
            )

    def close(self) -> None:
        self.__image_session = None
        self.__text_session = None
        self.__tokenizer = None

    def release(self) -> bool:
        with self.__lock:
            if self.__inflight > 0:
                return False
            self.close()
        return True
