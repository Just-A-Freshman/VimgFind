from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, fields
from typing import Literal
import ctypes
import logging


ROOT = Path(__file__).resolve().parent
SCALE_FACTOR = ctypes.windll.shcore.GetScaleFactorForDevice(0) / 100
def TkS(value: int | float, restore: bool = False) -> int:
    if not restore:
        return int(round(value * SCALE_FACTOR, 0))
    else:
        return int(round(value / SCALE_FACTOR, 0))
    
STATUS_LABEL = {
    "using": "正在使用",
    "downloaded": "可用",
    "not download": "不可用",
}

TYPE_LABEL = {
    "Image-Text": "图文模型",
    "Image": "纯图片模型",
    "Unknown": "未知",
}



@dataclass
class AppSettings:
    max_work_thread: int = 10
    max_match_count: int = 10
    preview_mode: Literal["detail_info", "medium_ico", "big_ico", "huge_ico"] = "medium_ico"
    auto_update_index: bool = True
    update_index_range: Literal["current", "all"] = "current"
    ui_style: str = "superhero"
    similarity_threshold: int = 48
    current_model: str = "chinese-clip"
    remote_manifest_url: str = "https://raw.githubusercontent.com/Just-A-Freshman/VimgFind/main/models.json"
    cache_ttl: int = 3600
    maximize_window: bool = False
    topmost_window: bool = False
    schedule_index_save_interval: int = 600000

    @classmethod
    def from_dict(cls, data: dict) -> AppSettings:
        valid = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in valid})


@dataclass
class ModelConfig:
    # --- meta_info section ---
    id: str = ""
    name: str = ""
    label: str = ""
    model_type: Literal["Image", "Image-Text", "Unknown"] = "Unknown"
    description: str = ""
    download_url: str = ""
    checksum_sha256: str = ""
    size: int = 0

    # --- model_config section ---
    image_size: int = 224
    preprocess_type: Literal["resize", "resize_crop", "resize_pad"] = "resize_crop"
    context_length: int = 52
    mean: tuple[float, float, float] = (0.48145466, 0.4578275, 0.40821073)
    std: tuple[float, float, float] = (0.26862954, 0.26130258, 0.27577711)
    normalization: bool = True
    image_encoder_path: str = ""
    text_encoder_path: str = ""
    vocab_path: str = ""

    # --- index_config section ---
    vector_index_path: str = ""
    name_index_path: str = ""
    index_capacity: int = 1000000
    index_dim: int = 512
    index_space: Literal["l2", "cosine"] = "cosine"
    search_dir: list[str] = field(default_factory=list)
    exclude_rules: list[str] = field(default_factory=list)

    _meta_keys = frozenset({
        "id", "name", "label", "model_type", "description", 
        "download_url", "checksum_sha256", "size"
    })
    _model_keys = frozenset({
        "image_size", "preprocess_type", "context_length", "mean", "std", "normalization",
        "image_encoder_path", "text_encoder_path", "vocab_path",
    })
    _index_keys = frozenset({
        "vector_index_path", "name_index_path",
        "index_capacity", "index_dim", "index_space",
        "search_dir", "exclude_rules",
    })

    @classmethod
    def from_dict(cls, data: dict) -> ModelConfig:
        merged: dict = {}
        merged.update(data.get("meta_info", {}))
        merged.update(data.get("model_config", {}))
        merged.update(data.get("index_config", {}))
        valid = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in merged.items() if k in valid})



class Setting(object):
    config_path = ROOT / "config"
    temp_image_path = ROOT / "temp"
    setting_path = config_path / "setting.json"
    models_dir = config_path / "models"
    temp_multi_search_queue = temp_image_path / "multi_search_queue.txt"
    error_log = config_path / "error.log"
    accepted_exts = {'.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.gif', '.webp'}

    def __init__(self) -> None:
        Path.mkdir(Setting.temp_image_path, exist_ok=True)
        self._app = self.load_app_config()
        self._model_cache: dict[str, ModelConfig] = {}

    @property
    def app(self) -> AppSettings:
        return self._app

    @property
    def model(self) -> ModelConfig:
        model_id = self._app.current_model
        if model_id not in self._model_cache:
            self._model_cache[model_id] = self.load_model_config(model_id)
        return self._model_cache[model_id]

    def use_model(self, model_id: str) -> None:
        self._app.current_model = model_id
        if model_id not in self._model_cache:
            self._model_cache[model_id] = self.load_model_config(model_id)

    def load_app_config(self) -> AppSettings:
        if Setting.setting_path.exists():
            with open(Setting.setting_path, "r", encoding="utf-8") as f:
                return AppSettings.from_dict(json.load(f))
        return AppSettings()

    def load_model_config(self, model_id: str) -> ModelConfig:
        model_path = self.models_dir / model_id / "model.json"
        if model_path.exists():
            with open(model_path, "r", encoding="utf-8") as f:
                return ModelConfig.from_dict(json.load(f))
        return ModelConfig()

    def clean_log(self) -> None:
        with open(Setting.error_log, "r", encoding="utf-8") as f:
            content = f.readlines()
        with open(Setting.error_log, "w", encoding="utf-8") as f:
            for line in content:
                try:
                    target_date = datetime.fromisoformat(line.split(" ")[0])
                    current_date = datetime.today()
                    delta_days = (current_date - target_date).days
                    if delta_days < 7:
                        f.write(line)
                except (ValueError, IndexError):
                    pass

    def get_model_list(self) -> list[str]:
        if not self.models_dir.exists():
            return []
        return sorted([
            d.name for d in self.models_dir.iterdir()
            if d.is_dir() and (d / "model.json").exists()
        ])

    def write_model_json(self, model_dir: Path, cfg: ModelConfig) -> None:
        meta_part: dict = {}
        model_part: dict = {}
        index_part: dict = {}
        for f in fields(ModelConfig):
            val = getattr(cfg, f.name)
            if f.name in ModelConfig._meta_keys:
                meta_part[f.name] = val
            elif f.name in ModelConfig._model_keys:
                model_part[f.name] = val
            elif f.name in ModelConfig._index_keys:
                index_part[f.name] = val
        model_path = model_dir / "model.json"
        with open(model_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "meta_info": meta_part,
                    "model_config": model_part,
                    "index_config": index_part,
                },
                f, indent=4, ensure_ascii=False,
            )

    def save_model_config(self, model_id: str, cfg: ModelConfig) -> None:
        self._model_cache[model_id] = cfg
        self.write_model_json(self.models_dir / model_id, cfg)

    def save(self) -> None:
        with open(Setting.setting_path, "w", encoding="utf-8") as f:
            app_dict = {f.name: getattr(self._app, f.name) for f in fields(AppSettings)}
            json.dump(app_dict, f, indent=4, ensure_ascii=False)
        for mid, cfg in self._model_cache.items():
            model_dir = self.models_dir / mid
            if model_dir.exists():
                self.write_model_json(model_dir, cfg)



class WinInfo(object):
    version = "2.5.1"
    repo_url = "https://github.com/Just-A-Freshman/VimgFind"
    ico_path = Setting.config_path / "favicon.ico"
    title = "Vimgfind"
    default_font_family = "微软雅黑"
    default_font_size = TkS(-14)
    width = TkS(830)
    height = TkS(560)



logging.basicConfig(
    filename=Setting.error_log,
    level=logging.ERROR,
    format='%(asctime)s -  %(message)s',
    encoding='utf-8'
)
