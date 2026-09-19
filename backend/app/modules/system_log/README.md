# system_log 模块

> 独立系统日志模块：`SystemLog` 记录“系统发生了什么”，`AuditLog` 记录“谁改了什么”。
> 与 notification、automation 分离，三者通过全局 Event Bus 解耦。

## 一、模块定位

```text
业务模块 publish 事件 -> EventBus 落库 AutomationEvent
    ├── system_log 监听器 -> SystemLog
    ├── notification 监听器 -> Notification / NotificationDelivery
    └── automation 监听器 -> AutomationTask
```

关键边界：

- Event 是内部通信，Log 是历史记录；
- Notification 负责触达，Automation 负责决定接下来执行什么；
- Audit Log 面向管理员操作，不通过 Event Bus，由关键管理动作直接写入。

## 二、目录结构

```text
system_log/
├── api/                       # 只读查询路由
├── application/               # 事件落日志、日志查询、审计写入
├── domain/                    # 级别/状态/资源映射规则
├── infrastructure/            # Event Bus 监听器
├── models/                    # SystemLog、AuditLog
├── repositories/              # 数据访问
└── schemas/                   # API DTO
```

## 三、数据模型

### system_logs

记录系统事件的结构化上下文，至少包含：

`level`、`event_type`、`module`、`actor_type/actor_id`、
`resource_type/resource_id`、`event_id`、`request_id`、`trace_id`、
`business_id`、`task_id`、`status`、`error_code`、`error_message`、
`context`、`created_at`。

日志由 `@listen("*")` 自动生成，业务模块无需直接写日志。

### audit_logs

记录管理操作：

`actor_id`、`actor_identifier`、`action`、`resource_type/resource_id`、
`before`、`after`、`changes`、`ip`、`user_agent`、`request_id`、
`event_id`、`created_at`。

审计日志不可通过 API 修改或删除；关键管理操作通过
`application/audit_log_create.py` 的 `record_audit_log` 写入。

## 四、API

所有接口均只读，并统一使用 `app/api/deps.py` 的 `require_permission` 声明权限码。

| 方法 | 路径 | 权限码 | 说明 |
| --- | --- | --- | --- |
| GET | /system-logs/ | `system_log:view` | 系统日志分页筛选 |
| GET | /system-logs/{log_id} | `system_log:view` | 系统日志详情 |
| GET | /audit-logs/ | `audit_log:view` | 操作审计分页筛选 |
| GET | /audit-logs/{audit_log_id} | `audit_log:view` | 操作审计详情 |

系统日志筛选参数：`level`、`module`、`event_type`、`status`、
`resource_type`、`resource_id`、`keyword`、`start_at`、`end_at`。

审计日志筛选参数：`action`、`resource_type`、`resource_id`、
`actor_id`、`keyword`、`start_at`、`end_at`。

## 五、关键设计

1. 业务模块只发布 `AutomationEvent`，系统日志监听器统一落库。
2. 日志监听器独立事务，失败只记录 Python 日志，不影响通知与自动化。
3. `module`、`level`、`status`、资源信息由 `domain/event_mapping.py` 自动推导。
4. `AuditLog` 只记录与操作相关的关键字段，不保存完整对象快照。
5. 按项目规范不提交 Alembic 迁移文件；上线时需执行
   `alembic revision --autogenerate` 与 `alembic upgrade head`。

## 六、使用说明

### 1. 系统日志

业务模块不需要直接调用日志模块，只需发布业务事件：

```python
backend/app/modules/system_log

publish_event(
    event_type="order.fulfillment_failed",
    payload={
        "order_id": "订单 UUID",
        "order_no": "ORD-1001",
        "vendor_id": "供应商 UUID",
        "error": {
            "code": "VENDOR_TIMEOUT",
            "message": "上游超时",
        },
    },
)
```

事件提交后，`system_log` 的全局监听器会自动写入 `SystemLog`，并根据
`domain/event_mapping.py` 推导 `module`、`level`、`status` 和关联资源。

### 2. 操作审计

关键管理操作由业务模块主动调用 `record_audit_log`：

```python
from app.modules.system_log.application.audit_log_create import record_audit_log

record_audit_log(
    session=session,
    actor=current_user,
    action="order.update_status",
    resource_type="order",
    resource_id=db_order.order_no,
    before={"status": old_status},
    after={"status": db_order.status},
    changes={
        "status": {
            "old": old_status,
            "new": db_order.status,
        },
    },
    ip=request.client.host if request.client else None,
    user_agent=request.headers.get("user-agent"),
    request_id=request.headers.get("x-request-id"),
)
```

当前已接入的操作：

- `order.cancel`
- `order.refund`
- `order.update_status`
- `wallet.adjust`

新增审计场景时，建议只记录与本次操作相关的字段，不保存完整对象快照。

### 3. 查询接口

管理端页面：

- `/system-logs`：系统日志
- `/audit-logs`：操作审计

对应 API 见上文第四节；所有接口均要求超管权限。

### 4. 上线迁移

按项目规范未提交 Alembic 迁移文件，新表需要在上线前手动生成并升级：

```bash
alembic revision --autogenerate -m "add system_logs and audit_logs"
alembic upgrade head
```
