from __future__ import annotations

import json
from config.settings import Setting


LOCALES_DIR = Setting.config_path / "locales"


class I18n:
    _instance: I18n | None = None

    def __new__(cls) -> I18n:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._locale = "zh-CN"
            cls._instance._translations = {}
        return cls._instance

    def load(self, locale: str) -> None:
        self._locale = locale
        self._translations = {}
        if locale == "zh-CN":
            return
        path = LOCALES_DIR / f"{locale}.json"
        if path.exists():
            self._translations = json.loads(path.read_text(encoding="utf-8"))

    def tr(self, text: str, **kwargs: str | int | float) -> str:
        if self._locale != "zh-CN":
            text = self._translations.get(text, text)
        return text.format(**kwargs) if kwargs else text

    @property
    def locale(self) -> str:
        return self._locale


def _(text: str, **kwargs: str | int | float) -> str:
    return I18n().tr(text, **kwargs)
