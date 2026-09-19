"""角色模块：数据访问层

只负责角色定义的查询与持久化；角色与权限、角色与用户的授予关系
见 authorization 模块，本文件不访问授权表。
"""

import uuid

from fastapi import HTTPException
from sqlalchemy.sql.elements import ColumnElement
from sqlmodel import Session, col, func, or_, select

from app.modules.role.models import Role


def create_role_row(
    *,
    session: Session,
    code: str,
    name: str,
    description: str | None,
    sort_order: int,
    is_system: bool,
    created_by: uuid.UUID | None,
) -> Role:
    """创建角色并加入会话（不提交，由调用方控制事务）"""
    role = Role(
        code=code,
        name=name,
        description=description,
        sort_order=sort_order,
        is_system=is_system,
        created_by=created_by,
    )
    session.add(role)
    session.flush()
    return role


def get_role(*, session: Session, role_id: uuid.UUID) -> Role | None:
    """按 ID 查询角色"""
    return session.get(Role, role_id)


def get_role_or_404(*, session: Session, role_id: uuid.UUID) -> Role:
    """按 ID 查询角色，不存在时抛出 404"""
    role = get_role(session=session, role_id=role_id)
    if role is None:
        raise HTTPException(status_code=404, detail="角色不存在")
    return role


def get_role_by_code(*, session: Session, code: str) -> Role | None:
    """按角色码查询角色"""
    return session.exec(select(Role).where(col(Role.code) == code)).first()


def delete_role_row(*, session: Session, role: Role) -> None:
    """删除角色行（不提交，由调用方控制事务）

    角色权限与用户角色分配由调用方先经 authorization 模块清理。
    """
    session.delete(role)
    session.flush()


def _role_filters(keyword: str | None) -> list[ColumnElement[bool]]:
    """角色列表筛选条件"""
    if not keyword or not keyword.strip():
        return []
    pattern = f"%{keyword.strip()}%"
    return [or_(col(Role.code).ilike(pattern), col(Role.name).ilike(pattern))]


def list_roles(
    *, session: Session, skip: int, limit: int, keyword: str | None = None
) -> list[Role]:
    """角色列表，按排序值与角色码升序"""
    statement = (
        select(Role)
        .where(*_role_filters(keyword))
        .order_by(col(Role.sort_order), col(Role.code))
        .offset(skip)
        .limit(limit)
    )
    return list(session.exec(statement).all())


def count_roles(*, session: Session, keyword: str | None = None) -> int:
    """角色总数（与列表同条件）"""
    statement = select(func.count()).select_from(Role).where(*_role_filters(keyword))
    return session.exec(statement).one()
