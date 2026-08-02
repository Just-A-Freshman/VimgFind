from __future__ import annotations

from pathlib import Path
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

    @classmethod
    def available_locales(cls) -> list[str]:
        locales = sorted(p.stem for p in LOCALES_DIR.glob("*.json") if p.stem != "zh-CN")
        return ["zh-CN", *locales]

    @classmethod
    def __resolve_path(cls, locale: str) -> Path:
        path = LOCALES_DIR / f"{locale}.json"
        if path.exists():
            return path
        base = locale.split("-")[0]
        path = LOCALES_DIR / f"{base}.json"
        return path if path.exists() else LOCALES_DIR / f"{locale}.json"

    @classmethod
    def locale_name(cls, locale: str) -> str:
        path = cls.__resolve_path(locale)
        try:
            data: dict = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return locale
        return data.get("__name__", locale)

    def load(self, locale: str) -> None:
        self._locale = locale
        self._translations = {}
        if locale == "zh-CN":
            return
        path = self.__resolve_path(locale)
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
