import json
from pathlib import Path



class Setting(object):
    config_path = Path("./config/setting.json")
    accepted_exts = {'.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.gif', '.webp'}
    schedule_save_interval = 600000

    def __init__(self) -> None:
        self.__config: dict = self.load_settings()
        self.__default_config = {
            "img_size": 260,
            "index_capacity": 1000000,
            "max_match_count": 30,
            "auto_update_index": True,
            "model_path": "config/models/imagenet-b2-opti.onnx",
            "index_path": "config/index/index.bin",
            "name_index_path": "config/index/name_index.json",
            "ui_style": "superhero",
            "search_dir": []
        }
    
    def get_config_property(self, key: str):
        if key in self.__default_config:
            if key not in self.__config:
                self.__config[key] = self.__default_config[key]
            return self.__config[key]
        else:
            raise KeyError(f"nonexist key: {key} in config！")

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


