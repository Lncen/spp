"""图片模块：业务逻辑层"""
import hashlib
import uuid
from datetime import datetime
from io import BytesIO
from pathlib import Path

from PIL import Image as PILImage
from PIL import ImageOps
from sqlmodel import Session, select

from app.core.config import settings
from app.modules.image.models import Image


def _compute_sha256(file_bytes: bytes) -> str:
    """计算文件 SHA256 哈希"""
    return hashlib.sha256(file_bytes).hexdigest()


_EXT_TO_FORMAT = {
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
    ".png": "PNG",
    ".webp": "WEBP",
}


def _get_upload_path(ext: str = ".webp") -> tuple[Path, str]:
    """生成文件存储路径：{UPLOAD_DIR}/images/{yyyy}/{mm}/{uuid}{ext}"""
    now = datetime.now()
    rel_dir = f"images/{now.year:04d}/{now.month:02d}"
    filename = f"{uuid.uuid4().hex}{ext}"
    rel_path = f"{rel_dir}/{filename}"
    abs_path = Path(settings.UPLOAD_DIR) / rel_path
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    return abs_path, rel_path


def process_and_save_image(
    *, session: Session, file_bytes: bytes, original_filename: str, owner_id: uuid.UUID, image_ext: str = ".webp"
) -> Image:
    """处理上传图片：去重 → 校验 → 缩略图 → 保存 → 返回记录

    如果已存在相同 SHA256 的图片，直接返回已有记录（零写入）。
    """
    # 1. 计算哈希，检查是否已存在
    file_hash = _compute_sha256(file_bytes)
    existing = session.exec(
        select(Image).where(Image.file_hash == file_hash)
    ).first()
    if existing:
        return existing

    # 2. 用 Pillow 打开并验证
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

        # 按原图格式输出缩略图
        save_format = _EXT_TO_FORMAT.get(image_ext, "WEBP")
        output = BytesIO()
        save_kwargs: dict = {"format": save_format, "optimize": True}
        if save_format in ("JPEG", "WEBP"):
            save_kwargs["quality"] = 85
        img.save(output, **save_kwargs)
        output_bytes = output.getvalue()
        width, height = img.size

    # 3. 写入磁盘
    abs_path, rel_path = _get_upload_path(image_ext)
    abs_path.write_bytes(output_bytes)

    # 4. 保存数据库记录
    db_image = Image(
        owner_id=owner_id,
        file_hash=file_hash,
        filename=original_filename,
        file_size=len(output_bytes),
        width=width,
        height=height,
        file_path=rel_path,
    )
    session.add(db_image)
    session.commit()
    session.refresh(db_image)
    return db_image
