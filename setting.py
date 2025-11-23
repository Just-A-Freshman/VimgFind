import json
from pathlib import Path



class Setting(object):
    config_path = Path("./config/setting.json")
    default_file_type = [("图片文件", "*.jpg;*.jpeg;*.png;*.bmp;*.gif;*.webp")]
    def __init__(self) -> None:
        self.config = self.load_settings()

    def load_settings(self):
        with open(Setting.config_path, encoding="utf-8") as f:
            return json.load(f)
        
    def save_settings(self):
        with open(Setting.config_path, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=4, ensure_ascii=False)


class WinInfo(object):
    ico_path = "config/favicon.ico"
    title = "以图搜图"
    width = 859
    height = 522


