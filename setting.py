import json
from pathlib import Path
from typing import Literal
from datetime import datetime
import logging




class Setting(object):
    config_path = Path("./config/setting.json")
    temp_image_path = Path("./temp")
    error_log = Path("./config/error.log")
    accepted_exts = {'.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.gif', '.webp'}
    schedule_save_interval = 600000

    def __init__(self) -> None:
        Path.mkdir(Setting.temp_image_path, exist_ok=True)
        self.__config: dict = self.load_settings()
        self.__default_config: dict = {
            "model_config": {
                "image_size": 0,
                "context_length": 0,
                "mean": [],
                "std": [],
                "normalization": False,
                "image_encoder_path": "NOTEXISTS",
                "text_encoder_path": "NOTEXISTS",
                "vocab_path": "NOTEXISTS"
            },
            "index_config": {
                "max_match_count": 30,
                "vector_index_path": "",
                "name_index_path": "",
                "index_capacity": 1000000,
                "index_space": "cosine",
                "index_dim": 512,
                "search_dir": []
            },
            "function_config": {
                "max_work_thread": 10,
                "auto_update_index": True,
                "preview_mode": "detail_info",
                "ui_style": "superhero"
            }
        }

    def clean_log(self) -> None:
        with open(Setting.error_log, "r", encoding="utf-8") as f:
            content = f.readlines()
        with open(Setting.error_log, "w", encoding="utf-8") as f:
            for line in content:
                try:
                    target_date = datetime.fromisoformat(line.split(" ")[0])
                    current_date = datetime.today()
                    delta_days = (target_date - current_date).days
                    if delta_days < 7:
                        f.write(line)
                except (ValueError, IndexError):
                    pass

    def get_config(self, config_type: Literal["model", "index", "function"], key: str):
        config_type_key = f"{config_type}_config"
        custom_config: dict = self.__config[config_type_key]
        default_config: dict = self.__default_config[config_type_key]
        if key not in default_config:
            logging.error(
                f"""Key '{key}' does not exist in {config_type_key}
                (valid keys: {list(default_config.keys())})"""
            )
        if key not in custom_config:
            self.__config[config_type_key][key] = default_config[key]
        elif type(custom_config[key]) != type(default_config[key]):
            self.__config[config_type_key][key] = default_config[key]
        
        return self.__config[config_type_key][key]

    def modity_config(self, config_type: Literal["model", "index", "function"], key: str, content) -> None:
        self.__config[f"{config_type}_config"][key] = content

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
    height = 555







logging.basicConfig(
    filename=Setting.error_log,
    level=logging.ERROR,
    format='%(asctime)s -  %(message)s',
    encoding='utf-8'
)

