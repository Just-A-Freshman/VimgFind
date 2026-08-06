from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Literal

@dataclass(slots=True)
class MetaInfo:
    id: str = ""
    name: str = ""
    label: str = ""
    model_type: Literal["Image", "Image-Text", "Unknown"] = "Unknown"
    description: str = ""
    download_url: str = ""
    checksum_sha256: str = ""
    size: int = 0


@dataclass(slots=True)
class EncoderConfig:
    image_size: int = 0
    preprocess_type: Literal["resize", "resize_crop", "resize_pad"] = "resize"
    fill_color: tuple[int, int, int] | None = None
    context_length: int = 0
    mean: tuple[float, float, float] = (0, 0, 0)
    std: tuple[float, float, float] = (0, 0, 0)
    normalization: bool = True
    output_index: int = 0
    image_encoder_path: str = ""
    text_encoder_path: str = ""


@dataclass(slots=True)
class IndexConfig:
    vector_index_path: str = ""
    name_index_path: str = ""
    index_capacity: int = 1000000
    index_dim: int = 512
    search_dir: list[str] = field(default_factory=list)
    exclude_rules: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ModelConfig:
    meta: MetaInfo = field(default_factory=MetaInfo)
    encoder: EncoderConfig = field(default_factory=EncoderConfig)
    index: IndexConfig = field(default_factory=IndexConfig)

    @classmethod
    def from_dict(cls, data: dict) -> ModelConfig:
        def _valid(cls_type, d):
            valid_keys = {f.name for f in fields(cls_type)}
            return {k: v for k, v in d.items() if k in valid_keys}

        return cls(
            meta=MetaInfo(**_valid(MetaInfo, data.get("meta_info", {}))),
            encoder=EncoderConfig(**_valid(EncoderConfig, data.get("model_config", {}))),
            index=IndexConfig(**_valid(IndexConfig, data.get("index_config", {}))),
        )


@dataclass(slots=True)
class MenuItemDef:
    name: str = "未命名"
    type: Literal["embedded", "separator", "custom"] = "custom"
    is_visible: bool = False
    shortcut: list[str] = field(default_factory=list)
    batch_mode: bool = False
    command: str = ""


@dataclass(slots=True)
class AppSettings:
    max_work_thread: int = 10
    max_match_count: int = 10
    preview_mode: Literal["detail_info", "medium_ico", "big_ico", "huge_ico"] = "medium_ico"
    auto_update_index: bool = True
    auto_update_idle_threshold: int = 300
    update_index_range: Literal["current", "all"] = "current"
    ui_style: str = "superhero"
    current_model: str = "osnet"
    remote_manifest_url: str = ""
    cache_ttl: int = 3600
    schedule_index_save_interval: int = 600
    maximize_window: bool = False
    topmost_window: bool = False
    locale: str = "zh-CN"
    menu_items: list[MenuItemDef] = field(default_factory=list)
    other_config_path: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> AppSettings:
        valid = {f.name for f in fields(cls)}
        result = cls(**{k: v for k, v in data.items() if k in valid})
        default_items = [MenuItemDef(name=id, type="embedded", is_visible=True) for id in ["复制图片", "复制路径", "图片另存为", "删除图片", "打开图片", "打开文件夹"]]
        if "menu_items" not in data:
            result.menu_items = default_items
        else:
            valid_menu_keys = {f.name for f in fields(MenuItemDef)}
            raw_embedded_items = set()
            filter_items = []
            for item in data["menu_items"]:
                menu_item = MenuItemDef(**{k: v for k, v in item.items() if k in valid_menu_keys})
                if menu_item.type != "embedded":
                    filter_items.append(menu_item)
                elif menu_item.name not in raw_embedded_items:
                    filter_items.append(menu_item)
                    raw_embedded_items.add(menu_item.name)
            for default in default_items:
                if default.name not in raw_embedded_items:
                    filter_items.append(default)
            result.menu_items = filter_items
        return result
