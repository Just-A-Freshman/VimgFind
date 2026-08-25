from __future__ import annotations

from dataclasses import fields, asdict
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
import ctypes
import json
import logging
import os
import subprocess
import urllib.parse

from .types import AppSettings, ModelConfig

ROOT = Path(__file__).resolve().parent.parent
SCALE_FACTOR = ctypes.windll.shcore.GetScaleFactorForDevice(0) / 100
def TkS(value: int | float) -> int:
    x = value * SCALE_FACTOR
    return 0 if x == 0 else max(int(round(abs(x), 0)), 1) * (-1 if x < 0 else 1)


class Setting:
    config_path = ROOT / "config" / "data"
    temp_image_path = ROOT / "temp"
    setting_path = config_path / "setting.json"
    models_dir = config_path / "models"
    manifest_cache = models_dir / "_manifest_cache.json"
    error_log = config_path / "error.log"
    ext_group_map: OrderedDict[str, set[str]] = OrderedDict({
        "PNG": {".png"},
        "JPG/JPEG": {".jpg", ".jpeg"},
        "WebP": {".webp"},
        "GIF": {".gif"},
        "BMP": {".bmp"},
        "TIFF": {".tiff", ".tif"},
        "PSD": {".psd"}
    })
    accepted_exts = [ext for group in ext_group_map.values() for ext in group]

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
        if not Setting.setting_path.exists():
            return AppSettings()
        with open(Setting.setting_path, "r", encoding="utf-8") as f:
            self._app = AppSettings.from_dict(json.load(f))
            active_config_path = self.get_active_config_path()
            if active_config_path == Setting.setting_path:
                return self._app
        with open(active_config_path, "r", encoding="utf-8") as f1:
            return AppSettings.from_dict(json.load(f1))

    def load_model_config(self, model_id: str) -> ModelConfig:
        model_path = Setting.models_dir / model_id / "model.json"
        if model_path.exists():
            with open(model_path, "r", encoding="utf-8") as f:
                return ModelConfig.from_dict(json.load(f))
        return ModelConfig()

    def clean_log(self) -> None:
        if not Path(Setting.error_log).exists():
            content = ""
        else:
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
            
    def link_to_docs(self, anchor: str = "") -> None:
        anchor = anchor.replace(" ", "-").lower()
        docs_dir = Setting.config_path / "docs"
        docs_path = docs_dir / f"help_{self.app.locale}.html"
        if not docs_path.exists():
            docs_path = docs_dir / "help_en-US.html"
        url = docs_path.as_uri() + "#" + urllib.parse.quote(anchor)
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"http\shell\open\command") as key:
                command = winreg.QueryValue(key, None)
            if "%1" in command:
                subprocess.Popen(command.replace("%1", f'"{url}"'), creationflags=subprocess.CREATE_NO_WINDOW)
                return
        except OSError:
            pass

    def get_active_config_path(self) -> Path:
        if self.app.other_config_path:
            other = Path(self.app.other_config_path)
            if other.exists():
                return other
        return Setting.setting_path

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
            app_dict["menu_items"] = [asdict(item) for item in self._app.menu_items]
            json.dump(app_dict, f, indent=4, ensure_ascii=False)
        for mid, cfg in self._model_cache.items():
            model_dir = self.models_dir / mid
            if model_dir.exists():
                self.write_model_json(model_dir, cfg)



class WinInfo:
    version = "2.5.3"
    repo_url = "https://github.com/Just-A-Freshman/VimgFind"
    icon_png = Setting.config_path / "favicon.png"
    title = "VimgFind"
    default_font = ("Microsoft YaHei", 9  if SCALE_FACTOR < 1.1 else 10)
    width = TkS(830)
    height = TkS(560)



logging.basicConfig(
    filename=Setting.error_log,
    level=logging.ERROR,
    format='%(asctime)s -  %(message)s',
    encoding='utf-8'
)
