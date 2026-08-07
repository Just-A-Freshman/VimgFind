from __future__ import annotations

import json

from config.settings import RESOURCE_DIR

LOCALES_DIR = RESOURCE_DIR / "locales"
LANGUAGES_FILE = LOCALES_DIR / "_languages.json"


class I18n:
    _instance: I18n | None = None

    def __new__(cls) -> I18n:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._locale = "zh-CN"
            cls._instance._translations = {}
        return cls._instance

    @classmethod
    def available_locales(cls) -> list[str]:
        locales = sorted(
            p.stem for p in LOCALES_DIR.glob("*.json")
            if not p.stem.startswith("_") and p.stem != "zh-CN"
        )
        return ["zh-CN", *locales]

    @classmethod
    def locale_name(cls, locale: str) -> str:
        try:
            data = json.loads(LANGUAGES_FILE.read_text(encoding="utf-8"))
            languages_name = data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            languages_name = {}
        return languages_name.get(locale, locale)

    def load(self, locale: str) -> None:
        self._locale = locale
        self._translations = {}
        if locale == "zh-CN":
            return
        
        path = LOCALES_DIR / f"{locale}.json"
        if not path.exists():
            base = locale.split("-")[0]
            path = LOCALES_DIR / f"{base}.json"
            path  = path if path.exists() else LOCALES_DIR / f"{locale}.json"

        self._translations = json.loads(path.read_text(encoding="utf-8"))

    def tr(self, text: str, **kwargs: str | int | float) -> str:
        if self._locale != "zh-CN":
            text = self._translations.get(text, text)
        return text.format(**kwargs) if kwargs else text


def _(text: str, **kwargs: str | int | float) -> str:
    return I18n().tr(text, **kwargs)
