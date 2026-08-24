"""备份文件本地存储"""

import gzip
import json
import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlmodel import Session

from app.core.config import settings
from app.core.time import get_datetime_cn
from app.modules.backup.domain.constants import (
    BACKUP_FILE_SUFFIX,
    BACKUP_META_SUFFIX,
    BACKUP_VERSION,
    DEFAULT_BACKUP_RETENTION_DAYS,
)
from app.modules.setting.application.setting_query import get_setting
from app.modules.setting.domain.constants import (
    BACKUP_DIR,
    BACKUP_RETENTION_DAYS,
)


def get_backup_dir(*, session: Session) -> Path:
    """解析备份目录，优先使用全局设置，其次使用环境变量。"""
    configured = get_setting(session=session, key=BACKUP_DIR)
    raw = configured if isinstance(configured, str) and configured.strip() else settings.BACKUP_DIR
    return Path(raw).expanduser().resolve()


def ensure_backup_dir(*, session: Session) -> Path:
    """确保备份目录存在并返回绝对路径。"""
    directory = get_backup_dir(session=session)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _backup_filename(created_at: datetime) -> str:
    stamp = created_at.astimezone(UTC).strftime("%Y%m%d_%H%M%S")
    return f"backup_{stamp}_{uuid.uuid4().hex[:8]}{BACKUP_FILE_SUFFIX}"


def write_backup(
    *,
    directory: Path,
    created_at: datetime,
    order_hours: int,
    counts: dict[str, int],
    data: dict[str, list[dict[str, Any]]],
) -> tuple[Path, str]:
    """写入压缩备份文件及同目录元数据文件。"""
    filename = _backup_filename(created_at)
    file_path = directory / filename
    meta_path = file_path.with_name(f"{file_path.name}{BACKUP_META_SUFFIX}")
    payload = {
        "version": BACKUP_VERSION,
        "created_at": created_at.isoformat(),
        "order_hours": order_hours,
        "counts": counts,
        "data": data,
    }
    payload_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    compressed = gzip.compress(payload_bytes, mtime=0)
    temp_path = file_path.with_name(f".{filename}.{uuid.uuid4().hex}.tmp")
    temp_path.write_bytes(compressed)
    os.replace(temp_path, file_path)

    metadata = {
        "version": BACKUP_VERSION,
        "filename": filename,
        "created_at": created_at.isoformat(),
        "size": file_path.stat().st_size,
        "order_hours": order_hours,
        "counts": counts,
    }
    meta_path.write_text(
        json.dumps(metadata, ensure_ascii=False),
        encoding="utf-8",
    )
    return file_path, filename


def read_backup_file(file_path: Path) -> dict[str, Any]:
    """读取并解压备份文件。"""
    with gzip.open(file_path, "rb") as f:
        return json.loads(f.read().decode("utf-8"))


def list_backup_files(directory: Path) -> list[dict[str, Any]]:
    """按创建时间倒序读取备份文件元数据。"""
    items: list[dict[str, Any]] = []
    for file_path in directory.glob(f"*{BACKUP_FILE_SUFFIX}"):
        meta_path = file_path.with_name(f"{file_path.name}{BACKUP_META_SUFFIX}")
        meta: dict[str, Any] = {}
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                meta = {}
        if not meta.get("created_at"):
            try:
                payload = read_backup_file(file_path)
            except (OSError, EOFError, json.JSONDecodeError):
                continue
            meta = {
                "filename": file_path.name,
                "created_at": payload.get("created_at"),
                "size": file_path.stat().st_size,
                "order_hours": payload.get("order_hours", settings.BACKUP_ORDER_HOURS),
                "counts": payload.get("counts", {}),
            }
        if not meta.get("created_at"):
            continue
        meta.setdefault("filename", file_path.name)
        meta.setdefault("size", file_path.stat().st_size)
        meta.setdefault("order_hours", settings.BACKUP_ORDER_HOURS)
        meta.setdefault("counts", {})
        items.append(meta)
    items.sort(key=lambda item: item.get("created_at") or "", reverse=True)
    return items


def resolve_backup_file(directory: Path, filename: str) -> Path:
    """安全解析备份文件路径，禁止路径穿越。"""
    if Path(filename).name != filename or not filename.endswith(BACKUP_FILE_SUFFIX):
        raise FileNotFoundError(filename)
    file_path = (directory / filename).resolve()
    if file_path.parent != directory:
        raise FileNotFoundError(filename)
    if not file_path.exists():
        raise FileNotFoundError(filename)
    return file_path


def delete_backup_file(file_path: Path) -> None:
    """删除备份文件和对应元数据文件。"""
    file_path.unlink(missing_ok=True)
    meta_path = file_path.with_name(f"{file_path.name}{BACKUP_META_SUFFIX}")
    meta_path.unlink(missing_ok=True)


def cleanup_old_backups(directory: Path, retention_days: int) -> int:
    """删除超过保留期的备份文件，返回删除数量。"""
    cutoff = get_datetime_cn() - timedelta(days=max(1, retention_days))
    deleted = 0
    for file_path in directory.glob(f"*{BACKUP_FILE_SUFFIX}"):
        meta_path = file_path.with_name(f"{file_path.name}{BACKUP_META_SUFFIX}")
        created_at_raw = None
        if meta_path.exists():
            try:
                created_at_raw = json.loads(meta_path.read_text(encoding="utf-8")).get(
                    "created_at"
                )
            except json.JSONDecodeError:
                created_at_raw = None
        if not created_at_raw:
            created_at_raw = datetime.fromtimestamp(
                file_path.stat().st_mtime, tz=UTC
            ).isoformat()
        try:
            created_at = datetime.fromisoformat(created_at_raw)
        except (TypeError, ValueError):
            created_at = datetime.fromtimestamp(file_path.stat().st_mtime, tz=UTC)
        if created_at < cutoff:
            delete_backup_file(file_path)
            deleted += 1
    return deleted


def get_retention_days(*, session: Session) -> int:
    """读取备份保留天数，非法值回退默认值。"""
    try:
        days = int(get_setting(session=session, key=BACKUP_RETENTION_DAYS))
    except (TypeError, ValueError):
        days = DEFAULT_BACKUP_RETENTION_DAYS
    return max(1, days)
