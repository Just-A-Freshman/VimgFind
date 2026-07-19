from __future__ import annotations

from collections import namedtuple
from typing import cast
import json
import re
import sys
import urllib.error
import urllib.request

from config.settings import WinInfo

UpdateCheckResult = namedtuple(
    "UpdateCheckResult",
    ["has_update", "latest_version", "release_url", "download_url", "release_body", "current_version", "error"]
)

API_URL = "https://api.github.com/repos/Just-A-Freshman/VimgFind/releases/latest"
_VERSION_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")


def _detect_platform_tag() -> str:
    system = sys.platform
    if system == 'win32':
        return 'win64'
    elif system == 'darwin':
        return 'macos'
    elif system.startswith('linux'):
        return 'linux-x64'
    return 'unknown'


def _parse_version(text: str) -> tuple[int, int, int] | None:
    m = _VERSION_RE.search(text)
    if m:
        return cast(tuple[int, int, int], tuple(int(g) for g in m.groups()))
    return None


def _find_latest_asset_version(assets: list[dict]) -> tuple[int, int, int] | None:
    best: tuple[int, int, int] | None = None
    for asset in assets:
        v = _parse_version(asset["name"])
        if v and (best is None or v > best):
            best = v
    return best


def _match_download_url(assets: list[dict], version: str) -> str | None:
    platform_tag = _detect_platform_tag()
    for asset in assets:
        if re.match(f"VimgFind-{version}-{platform_tag}-update", asset["name"]):
            return asset["browser_download_url"]
    return None


def check(timeout: int = 5) -> UpdateCheckResult:
    try:
        req = urllib.request.Request(
            API_URL,
            headers={
                "User-Agent": f"VimgFind/{WinInfo.version}",
                "Accept": "application/vnd.github.v3+json",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return UpdateCheckResult(
            False, "", "", "", "", WinInfo.version, f"HTTP {e.code}: {e.reason}"
        )
    except (urllib.error.URLError, OSError) as e:
        return UpdateCheckResult(
            False, "", "", "", "", WinInfo.version, f"网络错误: {e}"
        )
    except (json.JSONDecodeError, ValueError) as e:
        return UpdateCheckResult(
            False, "", "", "", "", WinInfo.version, f"响应解析失败: {e}"
        )

    release_url = data.get("html_url", WinInfo.repo_url)
    release_body = (data.get("body") or "").strip()
    assets = data.get("assets", [])

    latest_tuple = _find_latest_asset_version(assets)
    if latest_tuple is None:
        return UpdateCheckResult(
            False, "", "", "", "", WinInfo.version, "无法识别远程版本号"
        )

    latest_version = ".".join(str(g) for g in latest_tuple)
    current_tuple = _parse_version(WinInfo.version)
    has_update = current_tuple is not None and latest_tuple > current_tuple

    download_url = _match_download_url(assets, latest_version)

    return UpdateCheckResult(
        has_update, latest_version, release_url,
        download_url or release_url, release_body, WinInfo.version, None
    )
