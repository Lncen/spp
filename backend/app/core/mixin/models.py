import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime
from sqlmodel import Field


def get_datetime_utc() -> datetime:
    return datetime.now(UTC)


class TimestampMixin:
    """
    时间戳 Mixin，为所有表模型提供 created_at 和 updated_at 字段。
    注意：此类不包含 table=True，仅作为混入类使用。
    """
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True), # type: ignore
        nullable=False,
        title="创建时间",
        description="记录创建时的 UTC 时间，由系统自动生成，不可修改"
    )
    updated_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True), # type: ignore
        nullable=False,
        sa_column_kwargs={"onupdate": get_datetime_utc},
        title="更新时间",
        description="记录最近一次修改时的 UTC 时间，每次数据更新时由系统自动刷新"
    )


class UUIDPrimaryKeyMixin:
    """
    可选：顺便把 UUID 主键也抽象出来，进一步减少重复代码。
    """
    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        title="主键 ID",
        description="全局唯一的 UUID 标识符，由系统自动生成"
    )


class ActiveMixin:
    """通用状态字段 bool类型"""
    is_active: bool = Field(
        default=True,
        index=True,
        title="激活状态",
        description="标识该记录是否处于有效/激活状态，默认为 True"
    )


class SoftDeleteMixin:
    """软删除混入，is_deleted 标记 + deleted_at 时间戳"""
    is_deleted: bool = Field(
        default=False,
        index=True,
        title="软删除标记",
        description="标识该记录是否已被逻辑删除，默认为 False"
    )
    deleted_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True), # type: ignore
        nullable=True,
        title="删除时间",
        description="记录被逻辑删除时的 UTC 时间，未删除时为 None"
    )


class AuditUserMixin:
    """记录创建者和最后修改者的用户ID"""
    created_by: uuid.UUID | None = Field(
        default=None,
        foreign_key="user.id",
        title="创建者 ID",
        description="创建该记录的用户 UUID，关联 user 表"
    )
    updated_by: uuid.UUID | None = Field(
        default=None,
        foreign_key="user.id",
        title="最后修改者 ID",
        description="最后修改该记录的用户 UUID，关联 user 表"
    )


class VersionMixin:
    """乐观锁版本号，每次 UPDATE 时 version + 1"""
    version: int = Field(
        default=1,
        nullable=False,
        title="乐观锁版本号",
        description="用于并发控制的乐观锁版本号，每次数据更新时自动递增"
    )


class BaseModelMixin(UUIDPrimaryKeyMixin, TimestampMixin, ActiveMixin):
    """
    表模型的基类 Mixin
    ⚠️ 注意：这不是 table=True 的表，仅是混入基类
    包含字段：id, created_at, updated_at, is_active
    """
    pass
