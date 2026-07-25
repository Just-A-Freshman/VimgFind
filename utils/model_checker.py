from __future__ import annotations

from pathlib import Path
import json
import logging
import time
import urllib.error
import urllib.request as request
import zipfile

from config.settings import Setting
from config.types import ModelConfig


def validate_unknown_zip(zip_path: Path, model_id: str) -> ModelConfig:
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            namelist = zf.namelist()

            onnx_files = [n for n in namelist if n.endswith(".onnx")]
            if not onnx_files:
                raise AssertionError("无法识别的模型包：未找到 ONNX 模型文件（.onnx）。")

            if "model.json" not in namelist:
                raise AssertionError("无法识别的模型包：未找到 model.json 配置文件。")

            with zf.open("model.json") as f:
                raw = json.loads(f.read().decode("utf-8"))

            mc = raw.get("model_config") or {}
            image_path = mc.get("image_encoder_path", "") or ""
            text_path = mc.get("text_encoder_path", "") or ""

            if image_path and image_path not in namelist:
                raise AssertionError(f"校验失败：model.json 中的 image_encoder_path「{image_path}」在 zip 包中不存在。")
            if text_path and text_path not in namelist:
                raise AssertionError(f"校验失败：model.json 中的 text_encoder_path「{text_path}」在 zip 包中不存在。")

            raw["meta_info"] = raw.get("meta_info") or {"id": model_id, "name": model_id}
            return ModelConfig.from_dict(raw)

    except (zipfile.BadZipFile, json.JSONDecodeError) as e:
        raise AssertionError(f"无法读取模型包：{e}")


def fetch_remote_manifest(
    url: str,
    cache_path: Path,
    cache_ttl: int = 3600,
) -> list[dict] | None:
    now = time.time()
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            cache = json.load(f)
    except (json.JSONDecodeError, IOError, FileNotFoundError):
        cache = {}
    if now - cache.get("timestamp", 0) < cache_ttl:
        return cache.get("models")
    try:
        req = request.Request(url, headers={"Accept": "application/json"},)
        with request.urlopen(req, timeout=5) as resp:
            models: list[dict] = json.loads(json.loads(resp.read().decode("utf-8"))["raw_content"])
        
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump({"timestamp": now, "models": models}, f, indent=2)
        return models
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError, OSError) as e:
        logging.error(f"获取远程模型失败：{str(e)}")
        return cache.get("models")


def is_installed(setting: Setting, model_id: str) -> bool:
    model_dir = setting.models_dir / model_id
    return model_dir.is_dir() and (model_dir / "model.json").is_file()


def get_available_models(setting: Setting) -> list[ModelConfig]:
    cache_path = setting.manifest_cache
    installed_ids = setting.get_model_list()
    local_map: dict[str, ModelConfig] = {}
    result: list[ModelConfig] = []

    for mid in installed_ids:
        cfg = setting.load_model_config(mid)
        local_map[mid] = cfg
        result.append(cfg)

    remote_raw = fetch_remote_manifest(
        url=setting.app.remote_manifest_url,
        cache_path=cache_path,
        cache_ttl=setting.app.cache_ttl
    )
    if not remote_raw:
        return result
    for entry in remote_raw:
        meta = entry.get("meta_info") or {}
        mid = meta.get("id")
        if not mid:
            continue
        if mid in local_map:
            disk_cfg = local_map[mid]
            if not disk_cfg.meta.download_url:
                disk_cfg.meta.download_url = meta.get("download_url", "")
            if not disk_cfg.meta.checksum_sha256:
                disk_cfg.meta.checksum_sha256 = meta.get("checksum_sha256", "")
        else:
            result.append(ModelConfig.from_dict(entry))

    return result

