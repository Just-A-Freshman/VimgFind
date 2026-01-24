import json
from pathlib import Path
from typing import Literal
from datetime import datetime
import logging




class Setting(object):
    config_path = Path("./config/setting.json")
    help_path = Path("./config/readme.pdf")
    temp_image_path = Path("./temp")
    error_log = Path("./config/error.log")
    accepted_exts = {'.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.gif', '.webp'}
    schedule_save_interval = 600000

    def __init__(self) -> None:
        Path.mkdir(Setting.temp_image_path, exist_ok=True)
        self.__config: dict = self.load_settings()

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
        return self.__config[config_type_key][key]

    def modity_config(self, config_type: Literal["model", "index", "function"], key: str, content) -> None:
        self.__config[f"{config_type}_config"][key] = content

    def load_settings(self):
        with open(Setting.config_path, encoding="utf-8") as f:
            return json.load(f)
        
    def save_settings(self) -> None:
        with open(Setting.config_path, "w", encoding="utf-8") as f:
            json.dump(self.__config, f, indent=4, ensure_ascii=False)




class WinInfo(object):
    ico_path = "config/favicon.ico"
    title = "Vimgfind"
    width = 860
    height = 555







logging.basicConfig(
    filename=Setting.error_log,
    level=logging.ERROR,
    format='%(asctime)s -  %(message)s',
    encoding='utf-8'
)

