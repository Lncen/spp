"""数据备份接口"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import FileResponse

from app.api.deps import (
    CurrentUser,
    SessionDep,
    require_permission,
)
from app.common.models import Message
from app.modules.backup.application.create import create_backup as create_backup_service
from app.modules.backup.application.query import (
    get_backup_path,
    get_backup_payload,
    list_backups,
)
from app.modules.backup.application.restore import (
    restore_backup as restore_backup_service,
)
from app.modules.backup.infrastructure.storage import delete_backup_file
from app.modules.backup.schemas import (
    BackupPublic,
    BackupsPublic,
    RestoreResultPublic,
)
from app.modules.system_log.application.audit_log_create import record_audit_log

router = APIRouter(prefix="/backups", tags=["backups"])


def _request_meta(request: Request) -> tuple[str | None, str | None, str | None]:
    ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    request_id = request.headers.get("x-request-id")
    return ip, user_agent, request_id


@router.get(
    "/",
    dependencies=[Depends(require_permission("backup:view"))],
    response_model=BackupsPublic,
)
def read_backups(
    session: SessionDep,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> Any:
    """获取备份列表"""
    return list_backups(session=session, skip=skip, limit=limit)


@router.post(
    "/",
    dependencies=[Depends(require_permission("backup:create"))],
    response_model=BackupPublic,
)
def create_backup(
    *,
    request: Request,
    session: SessionDep,
    current_user: CurrentUser,
) -> Any:
    """手动创建数据备份"""
    result = create_backup_service(session=session)
    ip, user_agent, request_id = _request_meta(request)
    record_audit_log(
        session=session,
        actor=current_user,
        action="backup.create",
        resource_type="backup",
        resource_id=result.filename,
        after=result.model_dump(mode="json"),
        changes={"filename": {"old": None, "new": result.filename}},
        ip=ip,
        user_agent=user_agent,
        request_id=request_id,
    )
    return result


@router.get(
    "/{filename}/download",
    dependencies=[Depends(require_permission("backup:view"))],
)
def download_backup(
    *,
    session: SessionDep,
    filename: str,
) -> FileResponse:
    """下载备份文件"""
    file_path = get_backup_path(session=session, filename=filename)
    return FileResponse(
        path=file_path,
        media_type="application/gzip",
        filename=filename,
    )


@router.post(
    "/{filename}/restore",
    dependencies=[Depends(require_permission("backup:restore"))],
    response_model=RestoreResultPublic,
)
def restore_backup(
    *,
    request: Request,
    session: SessionDep,
    current_user: CurrentUser,
    filename: str,
) -> Any:
    """从指定备份执行合并恢复"""
    payload = get_backup_payload(session=session, filename=filename)
    result = restore_backup_service(session=session, payload=payload)
    ip, user_agent, request_id = _request_meta(request)
    record_audit_log(
        session=session,
        actor=current_user,
        action="backup.restore",
        resource_type="backup",
        resource_id=filename,
        after=result.model_dump(mode="json"),
        changes={"filename": {"old": None, "new": filename}},
        ip=ip,
        user_agent=user_agent,
        request_id=request_id,
    )
    return result


@router.delete(
    "/{filename}",
    dependencies=[Depends(require_permission("backup:delete"))],
    response_model=Message,
)
def delete_backup(
    *,
    request: Request,
    session: SessionDep,
    current_user: CurrentUser,
    filename: str,
) -> Any:
    """删除备份文件"""
    file_path = get_backup_path(session=session, filename=filename)
    delete_backup_file(file_path)
    ip, user_agent, request_id = _request_meta(request)
    record_audit_log(
        session=session,
        actor=current_user,
        action="backup.delete",
        resource_type="backup",
        resource_id=filename,
        changes={"filename": {"old": filename, "new": None}},
        ip=ip,
        user_agent=user_agent,
        request_id=request_id,
    )
    return Message(message="备份已删除")
