from __future__ import annotations
import subprocess
import tempfile
import threading
import zipfile
from pathlib import Path
from tkinter import messagebox

from utils import file_ops
from utils.i18n import _
from utils.model_checker import MultiThreadDownloader
from config.settings import ROOT
from views import UpdateDialog


class UpdateController:
    def __init__(self, app) -> None:
        self.app = app
        self._dialog: UpdateDialog | None = None
        self._downloader: MultiThreadDownloader | None = None
        self._temp_dir: Path | None = None
        self._cancelled = False

    def do_update(self, download_url: str, version: str) -> None:
        dialog = UpdateDialog(self.app.view, download_url, version)
        self._dialog = dialog
        self._downloader = None
        self._temp_dir = None
        self._cancelled = False

        dialog.protocol("WM_DELETE_WINDOW", self._on_cancel)

        threading.Thread(
            target=self._download_worker,
            args=(download_url, dialog),
            daemon=True,
        ).start()

    def _on_cancel(self) -> None:
        self._cancelled = True
        if self._downloader:
            self._downloader.cancel()
        self._cleanup()

    def _cleanup(self) -> None:
        if self._temp_dir and self._temp_dir.exists():
            file_ops.rmtree(self._temp_dir)
        self._temp_dir = None
        self._downloader = None
        dlg = self._dialog
        if dlg and dlg.winfo_exists():
            dlg.destroy()
        self._dialog = None

    def _download_worker(self, download_url: str, dialog: UpdateDialog) -> None:
        try:
            temp_dir = Path(tempfile.mkdtemp(prefix="vimgfind_update_"))
            zip_path = temp_dir / "update.zip"
            self._temp_dir = temp_dir

            def progress_cb(downloaded: int, total: int) -> None:
                if total > 0 and not self._cancelled:
                    pct = int(downloaded * 100 / total)
                    dialog.after(0, lambda: dialog.progressbar.config(value=pct))

            downloader = MultiThreadDownloader(
                url=download_url,
                save_path=str(zip_path),
                num_threads=16,
                progress_callback=progress_cb,
            )
            self._downloader = downloader
            downloader.download()

            if self._cancelled:
                return

            dialog.after(0, lambda: self._finish_update(zip_path))
        except RuntimeError as e:
            if "下载已取消" in str(e):
                return
            dialog.after(0, lambda: self._on_error(str(e)))
        except Exception as e:
            dialog.after(0, lambda: self._on_error(str(e)))

    def _finish_update(self, zip_path: Path) -> None:
        try:
            assert self._temp_dir is not None
            extract_dir = self._temp_dir / "extracted"
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
            self._cleanup()

    def _on_error(self, error_msg: str) -> None:
        messagebox.showerror(_("更新失败"), _("更新过程中出现错误：\n{msg}", msg=error_msg))
        self._cleanup()
