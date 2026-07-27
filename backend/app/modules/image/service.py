"""图片模块：业务逻辑层"""
import hashlib
import uuid
from datetime import datetime
from io import BytesIO
from pathlib import Path

from PIL import Image as PILImage
from PIL import ImageOps
from sqlalchemy import func as sa_func
from sqlmodel import Session, select

from app.core.config import settings
from app.modules.image.models import Image, ImageCategory
from app.modules.image.schemas import ImageCategoryCreate, ImageCategoryUpdate


# ===================== 图片上传（原有） =====================


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
    *, session: Session, file_bytes: bytes, original_filename: str, owner_id: uuid.UUID, image_ext: str = ".webp", category: str | None = None
) -> Image:
    """处理上传图片：去重 → 校验 → 缩略图 → 保存 → 返回记录

   如果已存在相同 SHA256 的图片，则更新已有记录的元数据（分类、文件名等）并返回。
    """
    # 1. 计算哈希，检查是否已存在
    file_hash = _compute_sha256(file_bytes)
    existing = session.exec(
        select(Image).where(Image.file_hash == file_hash)
    ).first()
    if existing:
        # 更新已有记录的元数据（分类、文件名等）
        old_category = existing.category
        updated = False
        if category is not None and existing.category != category:
            existing.category = category
            updated = True
        if existing.filename != original_filename:
            existing.filename = original_filename
            updated = True
        if updated:
            session.add(existing)
            session.commit()
            session.refresh(existing)
            # 分类变更时同步新旧分类的计数
            if old_category != category:
                sync_category_image_count(session=session, category_name=old_category)
                if category is not None:
                    sync_category_image_count(session=session, category_name=category)
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
        category=category,
    )
    session.add(db_image)
    session.commit()
    session.refresh(db_image)
    return db_image


# ===================== 分类管理（新增） =====================


def create_category(
    *, session: Session, data: ImageCategoryCreate
) -> ImageCategory:
    """创建图片分类"""
    category = ImageCategory(
        name=data.name,
        description=data.description,
        sort_order=data.sort_order,
        icon=data.icon,
        image_count=0,
    )
    session.add(category)
    session.commit()
    session.refresh(category)
    return category


def update_category(
    *, session: Session, category_id: uuid.UUID, data: ImageCategoryUpdate
) -> ImageCategory | None:
    """更新图片分类，返回更新后的对象；不存在则返回 None"""
    category = session.get(ImageCategory, category_id)
    if not category:
        return None

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(category, field, value)

    session.add(category)
    session.commit()
    session.refresh(category)
    return category


def delete_category(
    *, session: Session, category_id: uuid.UUID
) -> tuple[bool, str]:
    """删除图片分类。若分类下有图片引用则拒绝删除。
    返回 (success: bool, message: str)
    """
    category = session.get(ImageCategory, category_id)
    if not category:
        return False, "分类不存在"

    # 检查是否有图片引用该分类
    image_count = session.exec(
        select(sa_func.count()).select_from(Image).where(
            Image.category == category.name,
            Image.is_active == True,
        )
    ).one()
    if image_count > 0:
        return False, f"该分类下有 {image_count} 张图片，无法删除"

    session.delete(category)
    session.commit()
    return True, "分类已删除"


def get_category(
    *, session: Session, category_id: uuid.UUID
) -> ImageCategory | None:
    """根据 ID 获取分类"""
    return session.get(ImageCategory, category_id)


def get_category_by_name(
    *, session: Session, name: str
) -> ImageCategory | None:
    """根据 name 获取分类"""
    return session.exec(
        select(ImageCategory).where(ImageCategory.name == name)
    ).first()


def list_categories(
    *, session: Session, only_active: bool = False
) -> list[ImageCategory]:
    """获取分类列表，按 sort_order 升序排列"""
    query = select(ImageCategory)
    if only_active:
        query = query.where(ImageCategory.is_active == True)
    query = query.order_by(ImageCategory.sort_order, ImageCategory.name)
    return session.exec(query).all()


def list_category_options(
    *, session: Session
) -> list[str]:
    """获取分类选项名称列表"""
    categories = session.exec(
        select(ImageCategory)
        .where(ImageCategory.is_active == True)
        .order_by(ImageCategory.sort_order, ImageCategory.name)
    ).all()
    return [c.name for c in categories]


def sync_category_image_count(
    *, session: Session, category_name: str | None = None
) -> None:
    """同步指定分类（或所有分类）的 image_count 缓存值"""
    if category_name:
        categories = session.exec(
            select(ImageCategory).where(ImageCategory.name == category_name)
        ).all()
    else:
        categories = session.exec(select(ImageCategory)).all()

    for cat in categories:
        count = session.exec(
            select(sa_func.count()).select_from(Image).where(
                Image.category == cat.name,
                Image.is_active == True,
            )
        ).one()
        cat.image_count = count
        session.add(cat)

    if categories:
        session.commit()


def validate_category_name(
    *, session: Session, name: str
) -> tuple[bool, str]:
    """验证分类名称是否可用（存在且激活）
    返回 (is_valid: bool, message: str)
    """
    if not name:
        return False, "分类名称不能为空"
    category = session.exec(
        select(ImageCategory).where(ImageCategory.name == name)
    ).first()
    if not category:
        return False, f"分类 '{name}' 不存在"
    if not category.is_active:
        return False, f"分类 '{name}' 已禁用"
    return True, ""
