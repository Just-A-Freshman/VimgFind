import pathspec
from pathspec.patterns.gitwildmatch import GitWildMatchPattern

from settings import Setting


def _has_wildcard(pattern: str) -> bool:
    for ch in ("*", "?", "["):
        if ch in pattern:
            return True
    return False


def _normalize_rules(rules: list[str]) -> list[str]:
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


def compile_rules(rules: list[str] | None) -> "ExcludeRules | None":
    if not rules:
        return None
    return ExcludeRules(rules)


class ExcludeRules:
    """Compiled exclusion rules supporting full .gitignore semantics."""

    def __init__(self, rules: list[str]) -> None:
        normalized = _normalize_rules(rules)

        self._spec = pathspec.PathSpec.from_lines(
            GitWildMatchPattern,
            normalized,
        )

        # Build negation info for directory-skip optimization.
        # Unanchored negation patterns (no "/" after the "!") can match at any
        # level, so we can never skip a subtree when they exist.
        self._has_unanchored_negation = False
        self._anchored_negation: list[str] = []

        for rule in normalized:
            if not rule.startswith("!"):
                continue
            body = rule[1:]
            if body.startswith("/"):
                body = body[1:]
            if "/" not in body or _has_wildcard(body):
                self._has_unanchored_negation = True
            else:
                self._anchored_negation.append(body)

    def is_excluded(self, rel_path: str, is_dir: bool) -> bool:
        """Check if a relative path matches any exclusion rule."""
        normalized = rel_path.replace("\\", "/").lower()
        if is_dir and not normalized.endswith("/"):
            normalized += "/"
        if normalized.startswith("./"):
            normalized = normalized[2:]
        return self._spec.match_file(normalized)

    def is_affected_by_negation(self, dir_rel_path: str) -> bool:
        """Whether negation rules could rescue files under *dir_rel_path*.

        When *False* the caller may safely skip the entire subtree of a
        directory that *is_excluded* returned *True* for.
        """
        if self._has_unanchored_negation:
            return True
        if not self._anchored_negation:
            return False

        normalized = dir_rel_path.replace("\\", "/").lower()
        if not normalized.endswith("/"):
            normalized += "/"
        return any(p.startswith(normalized) for p in self._anchored_negation)


def is_accepted_extension(filename: str) -> bool:
    if not filename:
        return False
    dot = filename.rfind(".")
    if dot == -1:
        return False
    return filename[dot:].lower() in Setting.accepted_exts
