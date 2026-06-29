"""配置迁移与后向兼容工具。

集中管理所有配置格式迁移、物理文件迁移、路径修复逻辑。
Setting 类只需在 __init__ 中调用一次 run_config_migrations()。
"""

from pathlib import Path
import json


def _find_model_json(models_dir: Path, model_id: str) -> Path:
    return models_dir / model_id / "model.json"


def migrate_old_setting_format(config: dict, config_path: Path, models_dir: Path) -> bool:
    """将旧版 setting.json（含 model_config + index_config + function_config）迁移为新版。

    新版 setting.json 只存 current_model + 平铺的 function 配置。
    model_config + index_config 写入独立的 config/models/{model_id}/model.json。
    返回 True 表示配置已修改。
    """
    if "model_config" not in config:
        return False

    model_data = {
        "id": "chinese-clip",
        "name": "Chinese-CLIP",
        "version": "1.0.0",
        "type": "builtin",
        "source_url": None,
        "description": "Chinese-CLIP 模型，支持中英文图片和文字搜索",
        "checksum_sha256": None,
        "model_config": config.pop("model_config"),
        "index_config": config.pop("index_config"),
    }
    model_dir = models_dir / "chinese-clip"
    model_dir.mkdir(parents=True, exist_ok=True)
    with open(model_dir / "model.json", "w", encoding="utf-8") as f:
        json.dump(model_data, f, indent=4, ensure_ascii=False)

    config["current_model"] = "chinese-clip"
    # function_config 暂留在 config 中，由 flatten_function_config 处理
    return True


def flatten_function_config(config: dict) -> bool:
    """将 function_config 扁平化到 setting.json 顶层。"""
    if "function_config" not in config:
        return False
    for k, v in config.pop("function_config").items():
        config[k] = v
    return True


def move_model_files(models_dir: Path, model_config_cache: dict[str, dict]) -> None:
    """将平铺的模型文件和索引文件移到 chinese-clip 模型目录下。"""
    model_dir = models_dir / "chinese-clip"
    if (model_dir / "image_model.onnx").exists():
        return
    for fname in ["image_model.onnx", "text_model.onnx", "vocab.txt"]:
        src = models_dir / fname
        if src.exists():
            src.rename(model_dir / fname)
    index_dir = model_dir / "index"
    index_dir.mkdir(parents=True, exist_ok=True)
    parent_dir = models_dir.parent  # config/
    old_index = parent_dir / "index"
    for fname in ["vector_index.bin", "name_index.json"]:
        src = old_index / fname
        if src.exists():
            src.rename(index_dir / fname)
    update_model_json_paths(models_dir, "chinese-clip", model_config_cache)


def update_model_json_paths(models_dir: Path, model_id: str, model_config_cache: dict[str, dict]) -> None:
    """升级 model.json 中的路径，加入模型目录前缀。

    旧：config/models/image_model.onnx → 新：config/models/{model_id}/image_model.onnx
    旧：config/index/vector_index.bin → 新：config/models/{model_id}/index/vector_index.bin
    """
    model_data = model_config_cache.get(model_id)
    if not model_data:
        model_json = _find_model_json(models_dir, model_id)
        if model_json.exists():
            with open(model_json, encoding="utf-8") as f:
                model_data = json.load(f)
                model_config_cache[model_id] = model_data
        else:
            return

    changed = False
    mc = model_data.get("model_config", {})
    for key in ["image_encoder_path", "text_encoder_path", "vocab_path"]:
        old = mc.get(key, "")
        if old.startswith("config/models/"):
            mc[key] = f"config/models/{model_id}/{old[len('config/models/'):]}"
            changed = True
    ic = model_data.get("index_config", {})
    for key in ["vector_index_path", "name_index_path"]:
        old = ic.get(key, "")
        if old.startswith("config/index/"):
            ic[key] = f"config/models/{model_id}/index/{old[len('config/index/'):]}"
            changed = True

    if changed:
        model_path = _find_model_json(models_dir, model_id)
        with open(model_path, "w", encoding="utf-8") as f:
            json.dump(model_data, f, indent=4, ensure_ascii=False)


def fix_stripped_paths(models_dir: Path, model_config_cache: dict[str, dict]) -> None:
    """修复早期版本中被错误剥离路径前缀的问题。

    异常：image_model.onnx（缺少 config/models/chinese-clip/ 前缀）
    正常：config/models/chinese-clip/image_model.onnx
    """
    for model_id, model_data in model_config_cache.items():
        need_save = False
        mc = model_data.get("model_config", {})
        for key in ["image_encoder_path", "text_encoder_path", "vocab_path"]:
            val = mc.get(key, "")
            if val and not val.startswith("config/") and not val.startswith("\\") and ":" not in val:
                mc[key] = f"config/models/{model_id}/{val}"
                need_save = True
        ic = model_data.get("index_config", {})
        for key in ["vector_index_path", "name_index_path"]:
            val = ic.get(key, "")
            if val and not val.startswith("config/") and not val.startswith("\\") and ":" not in val:
                ic[key] = f"config/models/{model_id}/{val}"
                need_save = True
        if need_save:
            model_path = _find_model_json(models_dir, model_id)
            with open(model_path, "w", encoding="utf-8") as f:
                json.dump(model_data, f, indent=4, ensure_ascii=False)


def run_config_migrations(config_path: Path, models_dir: Path) -> tuple[dict, dict[str, dict]]:
    """运行所有配置迁移，返回 (config, model_config_cache)。

    在 Setting.__init__ 中单行调用。
    """
    with open(config_path, encoding="utf-8") as f:
        config = json.load(f)

    changed = False
    changed |= migrate_old_setting_format(config, config_path, models_dir)
    changed |= flatten_function_config(config)

    if "current_model" not in config:
        config["current_model"] = "chinese-clip"
        changed = True

    if changed:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)

    model_config_cache: dict[str, dict] = {}
    current_model = config.get("current_model", "chinese-clip")
    model_json = _find_model_json(models_dir, current_model)
    if model_json.exists():
        with open(model_json, encoding="utf-8") as f:
            model_config_cache[current_model] = json.load(f)

    move_model_files(models_dir, model_config_cache)
    fix_stripped_paths(models_dir, model_config_cache)

    return config, model_config_cache
