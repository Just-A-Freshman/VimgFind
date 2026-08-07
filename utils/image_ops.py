from __future__ import annotations

from pathlib import Path
import logging
import io

from PIL.ImageFile import ImageFile
from PIL import Image, UnidentifiedImageError
from AppKit import NSPasteboard, NSPasteboardTypePNG, NSPasteboardTypeTIFF

from . import internet
from . import file_ops
from config.settings import Setting


def parse_image_from_clipboard_bytes() -> None | ImageFile:
    try:
        pb = NSPasteboard.generalPasteboard()
        image_data = None
        for pasteboard_type in (NSPasteboardTypePNG, NSPasteboardTypeTIFF):
            data = pb.dataForType_(pasteboard_type)
            if data is not None:
                image_data = data.bytes()
                break
        if image_data is None:
            return None
        return Image.open(io.BytesIO(image_data))   # type: ignore[arg-type]
    except Exception:
        return None


def parse_image_from_path(image_path: str | Path) -> ImageFile | None:
    try:
        return Image.open(image_path)  # type: ignore[arg-type]
    except (UnidentifiedImageError, OSError, FileNotFoundError):
        return None


def parse_image_from_url(url: str) -> Image.Image | None:
    if not internet.validate_url_safe(url):
        return None

    url_lower = url.lower()
    is_likely_image = any(url_lower.endswith(ext) for ext in Setting.accepted_exts)
    try:
        with internet.fetch_url(url, timeout=10) as response:
            content_type = response.headers.get('Content-Type', '').lower()
            is_image_by_content = content_type.startswith('image/')
            if not is_image_by_content and not is_likely_image:
                raise ValueError(f"URL不是图像链接: Content-Type={content_type}, URL={url}")
            image_data = response.read(50 * 1024 * 1024)
            image: Image.Image = Image.open(io.BytesIO(image_data)).convert("RGB")
            return image
    except Exception as e:
        logging.warning(f"从URL解析图片失败: {e}")
        return None


def save_as_image(src_path: Path, dest_path : Path) -> bool:
    try:
        if dest_path.suffix.lower() == src_path.suffix.lower():
            if not file_ops.save_as(src_path, dest_path, True):
                raise Exception("系统权限错误！")
            return False
        img: Image.Image = Image.open(src_path)
        if dest_path.suffix.lower() in ('.jpg', '.jpeg') and img.mode == 'RGBA':
            img = img.convert('RGB')
        img.save(dest_path)
        return True
    except Exception as e:
        logging.error(f"图像保存时出现错误：{str(e)}")
        return False
