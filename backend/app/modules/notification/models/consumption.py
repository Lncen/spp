"""通知中心：事件消费状态模型

通知消费挂在全局 EventBus 上，而 EventBus 只保证「尽力分发」：
监听器抛错只记日志，自动化事件补发路径也不会重跑 EventBus 监听器。
因此通知消费自己记录状态，由定时任务重新消费未完成的记录：

```text
第一次消费失败 → 记录失败 → 定时重试 → dedupe_key 保证不重复 → 最终成功
```

可靠性靠重试，重复消费靠幂等。
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime
from sqlmodel import Field, SQLModel

from app.core.mixin.models import BaseModelMixin
from app.modules.notification.domain.constants import ConsumptionStatus


class NotificationEventConsumption(BaseModelMixin, SQLModel, table=True):
    """事件消费状态：一个自动化事件一行，记录是否已成功生成通知"""

    __tablename__ = "notification_event_consumptions"

    event_id: uuid.UUID = Field(
        index=True,
        nullable=False,
        unique=True,
        title="事件 ID",
        description="被消费的自动化事件 ID，不建外键以解耦事件清理策略",
    )
    status: str = Field(
        default=ConsumptionStatus.PENDING,
        max_length=16,
        index=True,
        nullable=False,
        title="消费状态",
        description="pending / processing / done / failed",
    )
    attempt_count: int = Field(
        default=0,
        nullable=False,
        title="已消费次数",
    )
    next_retry_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),  # type: ignore[call-overload]
        index=True,
        title="下次重试时间",
        description="失败后按指数退避写入，未到时间不会被重试任务认领",
    )
    last_error: str | None = Field(
        default=None,
        max_length=1000,
        title="最近一次失败原因",
    )
