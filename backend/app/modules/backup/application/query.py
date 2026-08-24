"""备份文件查询应用服务"""

from pathlib import Path

from fastapi import HTTPException
from sqlmodel import Session

from app.modules.backup.infrastructure.storage import (
    ensure_backup_dir,
    list_backup_files,
    read_backup_file,
    resolve_backup_file,
)
from app.modules.backup.schemas import (
    BackupCounts,
    BackupPublic,
    BackupsPublic,
)


def _to_public(meta: dict) -> BackupPublic:
    counts = meta.get("counts") or {}
    return BackupPublic(
        filename=meta.get("filename", ""),
        created_at=meta.get("created_at"),
        size=int(meta.get("size") or 0),
        order_hours=int(meta.get("order_hours") or 0),
        counts=BackupCounts.model_validate(counts),
    )


def list_backups(
    *,
    session: Session,
    skip: int,
    limit: int,
) -> BackupsPublic:
    """分页查询备份文件列表。"""
    directory = ensure_backup_dir(session=session)
    metas = list_backup_files(directory)
    data = [_to_public(meta) for meta in metas]
    return BackupsPublic(
        data=data[skip : skip + limit],
        count=len(data),
    )


def get_backup_path(*, session: Session, filename: str) -> Path:
    """解析备份文件路径，不存在或文件名非法时返回 404。"""
    directory = ensure_backup_dir(session=session)
    try:
        return resolve_backup_file(directory, filename)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="备份文件不存在") from exc


def get_backup_payload(*, session: Session, filename: str) -> dict:
    """读取指定备份文件的完整内容。"""
    return read_backup_file(get_backup_path(session=session, filename=filename))
