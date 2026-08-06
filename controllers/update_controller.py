from __future__ import annotations

from typing import TYPE_CHECKING, cast
from collections import namedtuple
from pathlib import Path
from tkinter import messagebox
import subprocess
import tempfile
import zipfile
import json
import sys
import re

from config.settings import ROOT, WinInfo
from views import UpdateDialog
from utils.i18n import _
import utils.file_ops as file_ops
import utils.internet as internet
import utils.decorators as decorators

if TYPE_CHECKING:
    from app_controller import AppController


API_URL = "https://api.github.com/repos/Just-A-Freshman/VimgFind/releases/latest"
VERSION_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")

UpdateCheckResult = namedtuple(
    "UpdateCheckResult",
    ["has_update", "latest_version", "release_url", "download_url", "release_body", "error"]
)


class UpdateController:
    def __init__(self, app_controller: AppController) -> None:
        self.app = app_controller
        self.__dialog: UpdateDialog | None = None
        self.__downloader: internet.MultiThreadDownloader | None = None
        self.__temp_dir: Path | None = None
        self.__cancelled = False

    def do_update(self, download_url: str, version: str) -> None:
        dialog = UpdateDialog(self.app.view)
        dialog.status_label.config(text=_("正在下载更新包 v{version}...", version=version))
        self.__dialog = dialog
        self.__downloader = None
        self.__temp_dir = None
        self.__cancelled = False
        dialog.protocol("WM_DELETE_WINDOW", self.__on_cancel)
        self.__download_worker(download_url, dialog)

    def check(self, timeout: int = 5) -> UpdateCheckResult:
        def parse_version(text: str) -> tuple[int, int, int] | None:
            m = VERSION_RE.search(text)
            return cast(tuple[int, int, int], tuple(int(g) for g in m.groups())) if m else None
        
        try:
            headers = {"User-Agent": f"VimgFind/{WinInfo.version}", "Accept": "application/vnd.github.v3+json"}
            with internet.fetch_url(API_URL, timeout=timeout, headers=headers) as response:
                data = json.loads(response.read().decode("utf-8"))
        except OSError as e:
            code = getattr(e, 'code', None)
            if code is not None:
                return UpdateCheckResult(False, "", "", "", "", f"HTTP {code}: {e}")
            return UpdateCheckResult(False, "", "", "", "", f"网络错误: {e}")
        except (json.JSONDecodeError, ValueError) as e:
            return UpdateCheckResult(False, "", "", "", "", f"响应解析失败: {e}")

        release_url = data.get("html_url", WinInfo.repo_url)
        release_body = (data.get("body") or "").strip()
        assets = data.get("assets", [])

        latest_tuple: tuple[int, int, int] | None = None
        for asset in assets:
            v = parse_version(asset["name"])
            if v and (latest_tuple is None or v > latest_tuple):
                latest_tuple = v

        if latest_tuple is None:
            return UpdateCheckResult(False, "", "", "", "", "无法识别远程版本号")

        latest_version = ".".join(str(g) for g in latest_tuple)
        current_tuple = parse_version(WinInfo.version)
        has_update = current_tuple is not None and latest_tuple > current_tuple

        system = sys.platform
        platform_tag = 'unknown'
        download_url = ""
        if system == 'win32':
            platform_tag = 'win64'
        elif system == 'darwin':
            platform_tag = 'macos'
        elif system.startswith('linux'):
            platform_tag = 'linux-x64'
        for asset in assets:
            if re.match(f"VimgFind-{latest_version}-{platform_tag}-update", asset["name"]):
                download_url = asset["browser_download_url"]

        if not download_url:
            return UpdateCheckResult(False, latest_version, release_url, "", "", "")

        return UpdateCheckResult(has_update, latest_version, release_url, download_url, release_body, None)

    def __on_cancel(self) -> None:
        self.__cancelled = True
        if self.__downloader:
            self.__downloader.cancel()
        self.__cleanup()

    def __cleanup(self) -> None:
        if self.__temp_dir and self.__temp_dir.exists():
            file_ops.rmtree(self.__temp_dir)
        self.__temp_dir = None
        self.__downloader = None
        dlg = self.__dialog
        if dlg and dlg.winfo_exists():
            dlg.destroy()
        self.__dialog = None

    @decorators.send_task
    def __download_worker(self, download_url: str, dialog: UpdateDialog) -> None:
        try:
            temp_dir = Path(tempfile.mkdtemp(prefix="vimgfind_update_"))
            zip_path = temp_dir / "update.zip"
            self.__temp_dir = temp_dir

            def progress_cb(downloaded: int, total: int) -> None:
                if total > 0 and not self.__cancelled:
                    pct = int(downloaded * 100 / total)
                    dialog.after(0, lambda: dialog.progressbar.config(value=pct))

            downloader = internet.MultiThreadDownloader(
                url=download_url,
                save_path=str(zip_path),
                num_threads=16,
                progress_callback=progress_cb,
            )
            self.__downloader = downloader
            downloader.download()

            if self.__cancelled:
                return

            dialog.after(0, lambda: self.__finish_update(zip_path))
        except RuntimeError as e:
            if "下载已取消" in str(e):
                return
            dialog.after(0, lambda: self.__on_error(str(e)))
        except Exception as e:
            dialog.after(0, lambda: self.__on_error(str(e)))

    def __finish_update(self, zip_path: Path) -> None:
        try:
            assert self.__temp_dir is not None
            extract_dir = self.__temp_dir / "extracted"
            extract_dir.mkdir(exist_ok=True)

            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(extract_dir)

            bat_path = extract_dir / "update.bat"
            if not bat_path.exists():
                found = list(extract_dir.rglob("update.bat"))
                bat_path = found[0] if found else None
            if not bat_path:
                raise FileNotFoundError("未找到 update.bat 安装脚本")
            subprocess.Popen(
                [str(bat_path), ROOT],
                shell=True,
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
            messagebox.showinfo(_("更新完成"), _("更新包已下载并安装，请重启程序以完成更新。"))
        except Exception as e:
            messagebox.showerror(_("更新失败"), _("更新过程中出现错误：\n{msg}", msg=str(e)))
        finally:
            self.__cleanup()

    def __on_error(self, error_msg: str) -> None:
        messagebox.showerror(_("更新失败"), _("更新过程中出现错误：\n{msg}", msg=error_msg))
        self.__cleanup()

