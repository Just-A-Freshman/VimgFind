from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, fields
from typing import Literal
import logging
import ctypes


ROOT = Path(__file__).resolve().parent


@dataclass
class AppSettings:
    max_work_thread: int = 10
    preview_mode: Literal["medium_ico", "detail_info"] = "medium_ico"
    auto_update_index: bool = True
    ui_style: str = "superhero"
    similarity_threshold: int = 48
    current_model: str = "chinese-clip"


@dataclass
class ModelConfig:
    # --- meta_info section ---
    id: str = ""
    name: str = ""
    version: str = ""
    description: str = ""
    download_url: str = ""
    checksum_sha256: str = ""

    # --- model_config section ---
    image_size: int = 224
    context_length: int = 52
    mean: tuple[float, float, float] = (0.48145466, 0.4578275, 0.40821073)
    std: tuple[float, float, float] = (0.26862954, 0.26130258, 0.27577711)
    normalization: bool = True
    image_encoder_path: str = ""
    text_encoder_path: str = ""
    vocab_path: str = ""

    # --- index_config section ---
    max_match_count: int = 100
    vector_index_path: str = ""
    name_index_path: str = ""
    index_capacity: int = 1000000
    index_dim: int = 512
    index_space: Literal["l2", "cosine"] = "cosine"
    search_dir: list[str] = field(default_factory=list)
    exclude_rules: list[str] = field(default_factory=list)

    _meta_keys = frozenset({
        "id", "name", "version", "description", "download_url", "checksum_sha256",
    })
    _model_keys = frozenset({
        "image_size", "context_length", "mean", "std", "normalization",
        "image_encoder_path", "text_encoder_path", "vocab_path",
    })
    _index_keys = frozenset({
        "max_match_count", "vector_index_path", "name_index_path",
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
    config_path = ROOT / "config" / "setting.json"
    models_dir = ROOT / "config" / "models"
    temp_image_path = ROOT / "temp"
    temp_multi_search_queue = temp_image_path / "multi_search_queue.txt"
    error_log = ROOT / "config" / "error.log"
    accepted_exts = {'.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.gif', '.webp'}
    schedule_save_interval = 600000

    def __init__(self) -> None:
        Path.mkdir(Setting.temp_image_path, exist_ok=True)
        self._app = AppSettings()
        self._model_cache: dict[str, ModelConfig] = {}
        self.__initialize()

    @property
    def app(self) -> AppSettings:
        return self._app

    @property
    def model(self) -> ModelConfig:
        model_id = self._app.current_model
        if model_id not in self._model_cache:
            self._model_cache[model_id] = self._load_model_config(model_id)
        return self._model_cache[model_id]

    def use_model(self, model_id: str) -> None:
        self._app.current_model = model_id
        if model_id not in self._model_cache:
            self._model_cache[model_id] = self._load_model_config(model_id)

    def __initialize(self) -> None:
        from utils.config_migration import run_config_migrations
        config_dict, model_cache_dicts = run_config_migrations(
            Setting.config_path, Setting.models_dir
        )
        app_fields = {f.name for f in fields(AppSettings)}
        for k, v in config_dict.items():
            if k in app_fields:
                setattr(self._app, k, v)
        for mid, data in model_cache_dicts.items():
            self._model_cache[mid] = ModelConfig.from_dict(data)

    def _load_model_config(self, model_id: str) -> ModelConfig:
        model_path = self.models_dir / model_id / "model.json"
        if model_path.exists():
            with open(model_path, "r", encoding="utf-8") as f:
                return ModelConfig.from_dict(json.load(f))
        return ModelConfig()

    def save(self) -> None:
        with open(Setting.config_path, "w", encoding="utf-8") as f:
            app_dict = {f.name: getattr(self._app, f.name) for f in fields(AppSettings)}
            json.dump(app_dict, f, indent=4, ensure_ascii=False)
        for mid, cfg in self._model_cache.items():
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
            model_path = self.models_dir / mid / "model.json"
            with open(model_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "meta_info": meta_part,
                        "model_config": model_part,
                        "index_config": index_part,
                    },
                    f, indent=4, ensure_ascii=False,
                )

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


class WinInfo(object):
    version = "2.5.1"
    repo_url = "https://github.com/Just-A-Freshman/VimgFind"
    scale_factor = ctypes.windll.shcore.GetScaleFactorForDevice(0) / 100
    ico_path = "config/favicon.ico"
    title = "Vimgfind"
    width = 830
    height = 560

    @staticmethod
    def TkS(value: int | float, restore: bool = False) -> int:
        if not restore:
            return int(round(value * WinInfo.scale_factor, 0))
        else:
            return int(round(value / WinInfo.scale_factor, 0))


logging.basicConfig(
    filename=Setting.error_log,
    level=logging.ERROR,
    format='%(asctime)s -  %(message)s',
    encoding='utf-8'
)
