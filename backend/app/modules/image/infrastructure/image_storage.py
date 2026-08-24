"""图片模块：图片处理与文件存储基础设施"""

import hashlib
import uuid
from io import BytesIO
from pathlib import Path

from PIL import Image as PILImage
from PIL import ImageOps

from app.core.config import settings
from app.core.time import get_datetime_cn


_EXT_TO_FORMAT = {
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
    ".png": "PNG",
    ".webp": "WEBP",
}


def compute_sha256(file_bytes: bytes) -> str:
    """计算文件 SHA256 哈希"""
    return hashlib.sha256(file_bytes).hexdigest()


def get_upload_path(ext: str = ".webp") -> tuple[Path, str]:
    """生成文件存储路径：{UPLOAD_DIR}/images/{yyyy}/{mm}/{uuid}{ext}"""
    now = get_datetime_cn()
    rel_dir = f"images/{now.year:04d}/{now.month:02d}"
    filename = f"{uuid.uuid4().hex}{ext}"
    rel_path = f"{rel_dir}/{filename}"
    abs_path = Path(settings.UPLOAD_DIR) / rel_path
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    return abs_path, rel_path


def process_image(file_bytes: bytes, image_ext: str = ".webp") -> tuple[bytes, int, int]:
    """用 Pillow 校验并处理图片：EXIF 旋转、RGBA 转 RGB、缩放、压缩

    返回 (输出字节, 宽度, 高度)。
    """
    with PILImage.open(BytesIO(file_bytes)) as img:
        # 应用 EXIF 旋转
        img = ImageOps.exif_transpose(img) or img

        # RGBA → 白色背景填充后转 RGB
        if img.mode == "RGBA":
            background = PILImage.new("RGBA", img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[3])
            img = background.convert("RGB")
        elif img.mode != "RGB":
            img = img.convert("RGB")

        # 缩放到最长边不超过 THUMBNAIL_MAX_DIMENSION
        max_dim = settings.THUMBNAIL_MAX_DIMENSION
        original_w, original_h = img.size
        if max(original_w, original_h) > max_dim:
            ratio = max_dim / max(original_w, original_h)
            new_w = int(original_w * ratio)
            new_h = int(original_h * ratio)
            img = img.resize((new_w, new_h), PILImage.LANCZOS)

        # 按原图格式输出
        save_format = _EXT_TO_FORMAT.get(image_ext, "WEBP")
        output = BytesIO()
        save_kwargs: dict = {"format": save_format, "optimize": True}
        if save_format in ("JPEG", "WEBP"):
            save_kwargs["quality"] = 85
        img.save(output, **save_kwargs)
        output_bytes = output.getvalue()
        width, height = img.size

    return output_bytes, width, height


def write_storage_file(rel_path: str, file_bytes: bytes) -> None:
    """写入图片文件到磁盘"""
    abs_path = Path(settings.UPLOAD_DIR) / rel_path
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_bytes(file_bytes)


def delete_storage_file(rel_path: str) -> None:
    """删除磁盘图片文件（不存在时静默跳过）"""
    file_path = Path(settings.UPLOAD_DIR) / rel_path
    if file_path.exists():
        file_path.unlink()
