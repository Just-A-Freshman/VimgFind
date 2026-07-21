from __future__ import annotations

from pathlib import Path
from typing import overload
from pathspec.patterns.gitwildmatch import GitWildMatchPattern
from datetime import datetime
import pathspec
import os
import re

from config.settings import Setting



def compile_rules(rules: list[str] | None) -> "ExcludeRules | None":
    if rules is None:
        return None
    return ExcludeRules(rules)


class ExcludeRules:
    SPECIAL_RULE_PATTERN = re.compile(
        r'^#(?P<key>min_size|max_size|min_modified|max_modified)\s*[:=]\s*(?P<value>.+)$',
        re.IGNORECASE,
    )

    def __init__(self, rules: list[str]) -> None:
        self._min_size: int = 0
        self._max_size: int = 0
        self._min_modified: float = 0.0
        self._max_modified: float = 0.0

        cleaned_rules = self.__extract_special_rules(rules)
        normalized = self.__normalize_rules(cleaned_rules)

        self._spec = pathspec.PathSpec.from_lines(GitWildMatchPattern, normalized)

        self._has_unanchored_negation = False
        self._anchored_negation: list[str] = []

        for rule in normalized:
            if not rule.startswith("!"):
                continue
            body = rule[1:]
            if body.startswith("/"):
                body = body[1:]
            if "/" not in body or self.__has_wildcard(body):
                self._has_unanchored_negation = True
            else:
                self._anchored_negation.append(body)

    # ── special rule parsing ──────────────────────────────────────

    def __extract_special_rules(self, rules: list[str]) -> list[str]:
        cleaned: list[str] = []
        for rule in rules:
            m = self.SPECIAL_RULE_PATTERN.match(rule.strip())
            if m:
                key = m.group("key").lower()
                raw_value = m.group("value").strip()
                try:
                    if key in ("min_size", "max_size"):
                        setattr(self, f"_{key}", self.__parse_size_value(raw_value))
                    elif key in ("min_modified", "max_modified"):
                        setattr(self, f"_{key}", self.__parse_modified_value(raw_value))
                except ValueError:
                    pass
            else:
                cleaned.append(rule)
        return cleaned

    @staticmethod
    def __parse_size_value(value_str: str) -> int:
        SIZE_VALUE_PATTERN = re.compile(
            r'^(\d+(?:\.\d+)?)\s*(kb|mb|b)?$', re.IGNORECASE
        )
        m = SIZE_VALUE_PATTERN.match(value_str.strip())
        if not m:
            raise ValueError(f"无法解析尺寸值: {value_str!r}")
        value = float(m.group(1))
        unit = (m.group(2) or "b").lower()
        multiplier = {"kb": 1024, "mb": 1024 ** 2, "b": 1}[unit]
        return int(value * multiplier)

    @staticmethod
    def __parse_modified_value(value_str: str) -> float:
        val = value_str.strip()
        try:
            dt = datetime.strptime(val, "%Y-%m-%d")
            return dt.timestamp()
        except ValueError:
            pass
        try:
            return float(val)
        except ValueError:
            raise ValueError(f"无法解析修改时间值: {val!r}")

    # ── normalization helpers ─────────────────────────────────────

    @staticmethod
    def __has_wildcard(pattern: str) -> bool:
        for ch in ("*", "?", "["):
            if ch in pattern:
                return True
        return False

    @staticmethod
    def __normalize_rules(rules: list[str]) -> list[str]:
        seen = set()
        normalized: list[str] = []
        for rule in rules:
            stripped = rule.strip()
            if not stripped or stripped.startswith("#"):
                continue
            lowered = stripped.lower()
            if lowered not in seen:
                seen.add(lowered)
                normalized.append(lowered)
        return normalized

    # ── pathspec helpers ──────────────────────────────────────────

    def _is_excluded(self, rel_path: str, is_dir: bool) -> bool:
        normalized = rel_path.replace("\\", "/").lower()
        if is_dir and not normalized.endswith("/"):
            normalized += "/"
        if normalized.startswith("./"):
            normalized = normalized[2:]
        return self._spec.match_file(normalized)

    def _is_affected_by_negation(self, dir_rel_path: str) -> bool:
        if self._has_unanchored_negation:
            return True
        if not self._anchored_negation:
            return False

        normalized = dir_rel_path.replace("\\", "/").lower()
        if not normalized.endswith("/"):
            normalized += "/"
        return any(p.startswith(normalized) for p in self._anchored_negation)

    def _is_accepted_extension(self, filename: str) -> bool:
        if not filename:
            return False
        dot = filename.rfind(".")
        if dot == -1:
            return False
        return filename[dot:].lower() in Setting.accepted_exts

    # ── public API ────────────────────────────────────────────────
    def should_skip_file(self, entry: os.DirEntry | str, target_dir: str) -> bool:
        path = entry if isinstance(entry, str) else entry.path
        if not self._is_accepted_extension(path):
            return True

        # Special rules (size, mtime) — stat only if needed
        has_size = self._min_size > 0 or self._max_size > 0
        has_mtime = self._min_modified > 0.0 or self._max_modified > 0.0
        if has_size or has_mtime:
            st = os.stat(entry) if isinstance(entry, str) else entry.stat()
            if has_size:
                if self._min_size > 0 and st.st_size < self._min_size:
                    return True
                if self._max_size > 0 and st.st_size > self._max_size:
                    return True
            if has_mtime:
                if self._min_modified > 0.0 and st.st_mtime < self._min_modified:
                    return True
                if self._max_modified > 0.0 and st.st_mtime > self._max_modified:
                    return True

        rel = os.path.relpath(path, target_dir).replace("\\", "/")
        return self._is_excluded(rel, is_dir=False)

    def should_skip_dir(self, entry: os.DirEntry | str, target_dir: str) -> bool:
        path = entry.path if isinstance(entry, os.DirEntry) else entry
        rel = os.path.relpath(path, target_dir).replace("\\", "/")
        if not self._is_excluded(rel, is_dir=True):
            return False
        return not self._is_affected_by_negation(rel)
