import json
from pathlib import Path
from typing import Literal



class Setting(object):
    config_path = Path("./config/setting.json")
    accepted_exts = {'.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.gif', '.webp'}
    schedule_save_interval = 600000

    def __init__(self) -> None:
        self.__config: dict = self.load_settings()
        self.__default_config: dict = {
            "model_config": {
                "image_size": 224,
                "context_length": 52,
                "mean": [0.48145466, 0.4578275, 0.40821073],
                "std": [0.26862954, 0.26130258, 0.27577711],
                "image_encoder_path": "config/clip_model/image_model.onnx",
                "text_encoder_path": "config/clip_model/text_model.onnx",
                "vocab_path": "config/clip_model/vocab.txt"
            },
            "index_config": {
                "max_match_count": 30,
                "vector_index_path": "config/index/vector_index.bin",
                "name_index_path": "config/index/name_index.json",
                "index_capacity": 1000000,
                "index_dim": 512,
                "search_dir": []
            },
            "function_config": {
                "max_work_thread": 10,
                "auto_update_index": True,
                "ui_style": "superhero"
            }
        }

    def get_config(self, config_type: Literal["model", "index", "function"], key: str):
        config_type_key = f"{config_type}_config"
        custom_config: dict = self.__config[config_type_key]
        default_config: dict = self.__default_config[config_type_key]
        if key not in default_config:
            raise KeyError(
                f"""Key '{key}' does not exist in {config_type_key}
                (valid keys: {list(default_config.keys())})"""
            )
        if key not in custom_config:
            self.__config[config_type_key][key] = default_config[key]
        elif type(custom_config[key]) != type(default_config[key]):
            self.__config[config_type_key][key] = default_config[key]
        
        return self.__config[config_type_key][key]
            
    def load_settings(self):
        try:
            with open(Setting.config_path, encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return self.__default_config
        
    def save_settings(self) -> None:
        with open(Setting.config_path, "w", encoding="utf-8") as f:
            json.dump(self.__config, f, indent=4, ensure_ascii=False)


class WinInfo(object):
    ico_path = "config/favicon.ico"
    title = "以图搜图"
    width = 860
    height = 530


