import io
import urllib.request
from pathlib import Path
from tkinter import filedialog, messagebox

import win32clipboard
import win32con
from PIL import Image, UnidentifiedImageError
from PIL.ImageFile import ImageFile

from settings import Setting
from . import file_ops


def parse_image_from_clipboard_bytes() -> None | ImageFile:
    try:
        win32clipboard.OpenClipboard()
        if not win32clipboard.IsClipboardFormatAvailable(win32con.CF_DIB):
            return None
        dib_data = win32clipboard.GetClipboardData(win32con.CF_DIB)
        return Image.open(io.BytesIO(dib_data))
    except Exception as e:
        return None
    finally:
        win32clipboard.CloseClipboard()


def parse_image_from_path(image_path: str | Path) -> ImageFile | None:
    try:
        return Image.open(image_path)
    except (UnidentifiedImageError, OSError, FileNotFoundError) as e:
        return


def parse_image_from_url(url: str) -> Image.Image | None:
    url_lower = url.lower()
    is_likely_image = any(url_lower.endswith(ext) for ext in Setting.accepted_exts)
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as response:
            content_type = response.headers.get('Content-Type', '').lower()
            is_image_by_content = content_type.startswith('image/')
            if not is_image_by_content and not is_likely_image:
                raise ValueError(f"URL不是图像链接: Content-Type={content_type}, URL={url}")
            image_data = response.read()
            image: Image.Image = Image.open(io.BytesIO(image_data)).convert("RGB")
            if hasattr(image, 'load'):
                image.load()
            return image
    except Exception:
        return


def save_as_image(src_path: Path) -> None:
    filetypes = [
        ("PNG 图片", "*.png"),
        ("JPEG 图片", "*.jpg"),
        ("WebP 图片", "*.webp"),
        ("BMP 图片", "*.bmp"),
        ("GIF 图片", "*.gif"),
        ("TIFF 图片", "*.tiff"),
    ]
    dest = filedialog.asksaveasfilename(
        defaultextension=src_path.suffix,
        filetypes=filetypes,
        initialfile=src_path.stem
    )
    if not dest:
        return
    dest = Path(dest)
    try:
        if dest.suffix.lower() == src_path.suffix.lower():
            if not file_ops.save_as(src_path, dest, True):
                raise Exception("系统权限错误！")
        img: Image.Image = Image.open(src_path)
        if dest.suffix.lower() in ('.jpg', '.jpeg') and img.mode == 'RGBA':
            img = img.convert('RGB')
        img.save(dest)
        return
    except Exception as e:
        messagebox.showerror("保存失败", str(e))
        return
