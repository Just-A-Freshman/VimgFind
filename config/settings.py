from __future__ import annotations

import json
import os
from pathlib import Path
from datetime import datetime
from dataclasses import fields, asdict
import ctypes
import logging

from .types import AppSettings, ModelConfig


ROOT = Path(__file__).resolve().parent.parent
SCALE_FACTOR = ctypes.windll.shcore.GetScaleFactorForDevice(0) / 100
def TkS(value: int | float, restore: bool = False) -> int:
    if not restore:
        return int(round(value * SCALE_FACTOR, 0))
    else:
        return int(round(value / SCALE_FACTOR, 0))

STATUS_LABEL = {
    "using": "使用中",
    "downloading": "下载中",
    "downloaded": "可用",
    "not download": "不可用",
}

TYPE_LABEL = {
    "Image-Text": "多模态",
    "Image": "图像",
    "Unknown": "未知",
}

RANGE_LABEL = {
    "current": "当前模型",
    "all": "全部模型"
}


class Setting(object):
    config_path = ROOT / "config" / "data"
    temp_image_path = ROOT / "temp"
    setting_path = config_path / "setting.json"
    models_dir = config_path / "models"
    temp_multi_search_queue = temp_image_path / "multi_search_queue.txt"
    manifest_cache = models_dir / "_manifest_cache.json"
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
        os.chdir(Setting.models_dir / model_id)
        if model_id not in self._model_cache:
            self._model_cache[model_id] = self.load_model_config(model_id)
        return self._model_cache[model_id]

    def load_app_config(self) -> AppSettings:
        if Setting.setting_path.exists():
            with open(Setting.setting_path, "r", encoding="utf-8") as f:
                return AppSettings.from_dict(json.load(f))
        return AppSettings()

    def load_model_config(self, model_id: str) -> ModelConfig:
        model_path = Setting.models_dir / model_id / "model.json"
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
        model_path = model_dir / "model.json"
        with open(model_path, "w", encoding="utf-8") as f:
            json.dump({
                "meta_info": asdict(cfg.meta),
                "model_config": asdict(cfg.encoder),
                "index_config": asdict(cfg.index),
            }, f, indent=4, ensure_ascii=False)

    def save_model_config(self, model_id: str, cfg: ModelConfig) -> None:
        self._model_cache[model_id] = cfg
        self.write_model_json(self.models_dir / model_id, cfg)

    def remove_model_config(self, model_id: str) -> None:
        self._model_cache.pop(model_id, None)

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
    title = "VimgFind"
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
