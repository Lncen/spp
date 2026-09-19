# automation 模块

> 全局业务自动化引擎：计划任务管理 + 「事件 → 规则 → 任务 → 执行器」任务池，
> 并统一收敛全项目 Celery 定时任务。

## 一、模块定位

`automation` 是**全局自动化引擎**，不是某个业务模块（如订单）的附属功能，
只负责「何时触发、失败怎么重试、结果怎么归档」：

- **计划任务**：管理 `PeriodicTask`（crontab / interval），支持启停、立即执行、执行状态查询；
- **自动化任务池**：`AutomationTask` 持久化业务任务，worker 扫描认领后交给 Executor 执行，
  失败按 `max_retry` 自动重试；
- **任务归档与保留**：终态任务（`success` / `failed` / `canceled`）完成即移入
  `AutomationTaskArchive`，按全局保留期到期物理删除；
- **事件驱动**：业务事件落库 `AutomationEvent` → 按启用规则 `AutomationRule` 生成任务，
  分发失败按退避时间补发；
- **定时任务统一收敛**：全项目 Celery 定时任务统一放在 `infrastructure/tasks/`，
  任务名统一为 `app.modules.automation.infrastructure.tasks.*`。

**不负责**：

- **业务规则与业务流程**：订单履约编排在 `order/application/fulfillment.py`，订单状态同步
  编排在 `order/application/sync.py`，上游 API 能力在 `supplier` 模块，automation 只负责触发；
- **业务事件的定义与发布**：事件由业务模块通过 `app/core/event_bus.py` 发布，automation 只消费；
- **前端页面实现**：后端只提供接口，页面在 `frontend/src/components/Admin/Automation/`。

核心链路：

```text
业务事件 → AutomationRule → AutomationTask → Executor
    ↑                                  ↑
event_bus.publish              Celery Worker

Celery beat → PeriodicTask → infrastructure/tasks/* → 各业务模块能力
```

## 二、目录结构

```text
backend/app/modules/automation/
├── __init__.py
├── README.md                       # 本文件：模块定位、结构与约定
├── api/                            # 接口层：仅路由，不含业务逻辑
│   ├── __init__.py                 # 导出 automation_router、automation_events_router、automation_rules_router、schedule_router、schedule_tasks_router
│   ├── automation.py               # /automation/tasks：任务池列表 / 创建 / 详情 / 归档 / 重试 / 取消 / 执行器选项
│   ├── events.py                   # /automation/events：事件列表与手动发布
│   ├── rules.py                    # /automation/rules：规则 CRUD 与启停
│   ├── schedules.py                # /schedules：列表 / 详情 / 更新 / 启停 / 立即执行 / Celery 任务选项
│   └── tasks.py                    # /schedules/tasks/{task_id}/status：Celery 任务执行状态
├── application/                    # 应用服务：按业务能力归组，同一能力不拆成多个文件
│   ├── __init__.py
│   ├── task.py                     # 任务池：创建 / 查询 / 归档查询 / 取消 / 重试 / 执行器清单 / 来源组装
│   ├── task_execution.py           # 任务池执行状态流转（成功归档 / 失败重试 / 业务终态失败）
│   ├── event.py                    # 事件：发布 / 列表查询 / 按规则分发生成任务
│   ├── rule.py                     # 规则：创建 / 更新 / 启停 / 删除 / 查询
│   └── schedule.py                 # 计划任务：查询 / 更新 / 启停 / 立即执行 + Celery 任务清单与状态
├── domain/                         # 领域逻辑：不依赖 Web 框架 / 数据库 / Celery
│   ├── __init__.py
│   ├── constants.py                # 状态枚举、终态任务集合、事件类型中文展示名
│   ├── execution.py                # 任务执行规则：失败后重试 / 终态判定、可取消与可重试判定
│   └── validation.py               # crontab / interval 配对校验、规则配置 task_options 校验
├── infrastructure/                 # 基础设施：Celery、执行器、定时任务
│   ├── __init__.py
│   ├── celery.py                   # 任务发现、立即发送、状态查询、TASK_LABELS
│   ├── beat_schedule.py            # Celery beat 初始调度种子（init_tasks）
│   ├── event_listeners.py          # @listen("*")：事件落库后按规则生成任务
│   ├── executors/                  # 任务执行器（注册机制）
│   │   ├── __init__.py             # 导入内置执行器并导出 EXECUTORS 注册表
│   │   ├── base.py                 # BaseExecutor + register_executor + get_executor + ExecutorTerminalError
│   │   ├── log.py                  # log：通用占位执行器（仅写日志）
│   │   ├── order_submit.py         # submit_supplier_order：API 订单向上游提交履约
│   │   └── order_refund.py         # apply_supplier_refund：API 订单向上游申请退单
│   └── tasks/                      # 全项目 Celery 定时任务（按职责拆分，包内统一导出）
│       ├── __init__.py
│       ├── scan.py                 # automation_task_scan：任务池扫描执行
│       ├── event_redispatch.py     # redispatch_stale_automation_events：事件补发
│       ├── cleanup.py              # cleanup_automation_task_archives：归档与事件清理
│       ├── order_status.py         # sync_order_status_periodic：订单状态同步
│       ├── order_cleanup.py        # cleanup_completed_orders：已完成订单数据清理
│       ├── product_sync.py         # sync_product_status：已同步商品成本价 / 关单状态分发
│       ├── supplier_sync.py        # sync_upstream_products + dispatch_upstream_products_sync：上游商品同步
│       ├── notification_delivery.py  # deliver_notification + requeue_stale_notification_deliveries：通知投递与兜底扫描
│       ├── notification_cleanup.py # cleanup_notification_records：通知记录清理
│       ├── wallet_cleanup.py       # cleanup_wallet_transactions：钱包流水清理
│       ├── auth_cleanup.py         # cleanup_expired_refresh_tokens：过期刷新令牌清理
│       ├── expired_data.py         # cleanup_expired_data：过期数据 / 临时文件清理
│       └── retention.py            # 统一读取全局保留期设置（清理任务共用）
├── models/                         # 数据模型（SQLModel 表模型）
│   ├── __init__.py
│   ├── task.py                     # AutomationTask：任务池（状态、优先级、重试、payload、来源、时间线）
│   ├── archive.py                  # AutomationTaskArchive：终态归档（task_id 保留原任务 ID）
│   ├── event.py                    # AutomationEvent：业务事件（分发状态、次数、错误、时间线）
│   └── rule.py                     # AutomationRule：事件 → 动作规则
├── repositories/                   # 数据访问：封装 ORM 操作，不承载流程编排
│   ├── __init__.py
│   ├── task.py                     # 任务池：查询、原子认领、状态持久化原语、归档与清理
│   ├── event.py                    # 事件：创建、查询、补发认领、批量事件类型、清理
│   ├── rule.py                     # 规则：创建、查询、启用规则查询、批量名称映射
│   └── schedule.py                 # PeriodicTask / CrontabSchedule / IntervalSchedule 访问
└── schemas/                        # 数据传输对象
    ├── __init__.py
    ├── automation.py               # 任务 / 归档 / 事件 / 规则 DTO
    └── schedule.py                 # 计划任务 / 任务选项 / 任务状态 DTO
```

全局事件总线位于 `app/core/event_bus.py`（业务模块只依赖 core，避免反向依赖 automation）。

## 三、分层职责

| 层 | 职责 | 本模块内容 |
| --- | --- | --- |
| api | 权限验证、接收请求、参数校验、调用 Application、返回响应 | 任务池、事件、规则、计划任务路由（均声明权限码） |
| application | 编排业务流程、控制事务 | 任务池管理与执行流转、事件发布与分发、规则 CRUD、计划任务管理 |
| domain | 核心业务规则，不依赖 Web 框架 / 数据库 / Celery | 状态枚举与终态集合、重试与状态流转判定、调度配对与规则配置校验 |
| infrastructure | 外部系统交互 | Celery 任务发现与 beat 种子、事件监听器、执行器注册表、定时任务 |
| repositories | 数据查询与数据持久化 | 任务池原子认领与状态持久化、事件与规则存取、计划任务表访问 |
| models | 数据模型 | AutomationTask / AutomationTaskArchive / AutomationEvent / AutomationRule |
| schemas | 数据传输对象 | 请求 / 响应 DTO |

## 四、核心职责

- **计划任务管理**：`/schedules` 提供列表、详情、更新（可切换 crontab / interval）、启停、
  立即执行一次、Celery 任务执行状态查询；可配置任务清单供前端下拉。
- **任务池**：`/automation/tasks` 提供创建一次性任务、列表与详情、归档列表、失败任务重新入队、
  待执行任务取消；任务来源（事件类型展示名、规则名称）随响应返回。
- **事件驱动**：`/automation/events` 提供事件列表与手动发布；落库事件按启用规则生成任务，
  分发失败的事件由定时任务按退避时间补发。
- **规则管理**：`/automation/rules` 提供 CRUD 与启停；规则的 `config` 合并进任务 payload，
  保留键 `task_options` 用于配置 `priority` / `max_retry` / `delay_seconds`。
- **执行器机制**：`infrastructure/executors/` 提供执行器基类与注册表，
  注册后的 `task_type` 才能用于规则动作与手动创建任务。
- **定时任务与数据保留**：`infrastructure/tasks/` 收敛全项目定时任务，
  并按全局设置保留期清理归档、事件、订单、钱包流水、通知等历史数据。

当前 beat 初始调度（种子在 `infrastructure/beat_schedule.py`，以该文件为准）：

| 任务 | 触发周期 |
| --- | --- |
| `automation_task_scan` | 30 秒 |
| `redispatch_stale_automation_events` | 1 分钟 |
| `requeue_stale_notification_deliveries` | 5 分钟 |
| `sync_order_status_periodic` | 1 小时 |
| `sync_product_status` | 1 小时 |
| `cleanup_completed_orders` | 每天 03:00 |
| `cleanup_notification_records` | 每天 03:30 |
| `cleanup_automation_task_archives` | 每天 04:00 |
| `cleanup_wallet_transactions` | 每天 04:30 |
| `cleanup_expired_refresh_tokens` | 每天 05:00 |
| `cleanup_expired_data` | 每天 05:30 |
| `app.modules.backup.infrastructure.tasks.create_backup` | 每天 02:00 |

## 五、关键流程

### 1. 事件驱动链路（一次事件 → 若干任务）

```text
业务模块 event_bus.publish(event_type, payload)
        ↓
AutomationEvent 落库（pending）→ 事件监听器 @listen("*")
        ↓
AutomationRule 按 event_type 匹配（仅 is_active=True）
        ↓
payload = 事件载荷 + 规则 config（同名参数以规则为准，task_options 不进 payload）
        ↓
AutomationTask 落库（来源记录 event_id / rule_id）
```

- 规则的 `task_options.delay_seconds > 0` 时任务 `execute_at` 顺延，到期才会被认领；
- 分发成功：事件置 `dispatched`、分发次数 +1、清空最近错误与补发时间；
- 分发失败：事件置 `failed`，按 `60s × 2^(n-1)`（上限 1 小时）设置下次补发时间。

### 2. 任务池执行链路

```text
beat（30 秒）→ automation_task_scan
        ↓ 恢复失联 running（超过 10 分钟未推进）
        ↓ 原子认领到期 pending（UPDATE ... RETURNING，单次上限 500）
        ↓ Executor.check_already_done()：业务目标已达成 → 直接成功归档
        ↓ Executor.execute()
        ↓ 成功 → 移入归档表；失败 → 回退 pending 重试 / 重试耗尽进 failed 终态
```

- 认领采用 `UPDATE ... RETURNING`，多 worker 并发只返回本事务真正认领的行；
- 执行前推进 `started_at` / `updated_at`，长批次执行不会被误判为失联；
- 执行器抛 `ExecutorTerminalError`（业务已终态，如订单转人工确认）时跳过重试直接失败归档；
- 落终态时按认领令牌锁定任务行，任务已被他人接管则放弃写入。

### 3. 事件补发链路

`redispatch_stale_automation_events` 每分钟扫描未分发 / 分发中 / 分发失败的事件
（分发次数 < 5，且到达补发时间或已过 60 秒宽限期），原子认领后逐条重新分发；
已被 worker 崩溃打断的“分发中”事件会在认领后重新生成任务。

### 4. 计划任务链路

```text
init_tasks（beat_schedule.py，启动时写入数据库作初始种子）
        ↓
PeriodicTask（crontab / interval，可在 /schedules 更新配置与启停）
        ↓
Celery beat 触发 → infrastructure/tasks/* → 业务模块能力
```

`/schedules/{id}/run` 可立即执行一次且不影响原计划，返回 Celery 任务 ID，
配合 `/schedules/tasks/{task_id}/status` 查询执行状态。

### 5. 数据保留与清理链路

`cleanup_automation_task_archives` 每天 04:00 先兜底归档任务池中遗留的终态任务，
再按同一保留期同步物理删除超期归档与事件数据；订单、钱包流水、通知记录的清理
由各自定时任务按对应设置键执行，均分批处理避免长事务。

## 六、重要约定

1. **执行器幂等强制**：任务池是 at-least-once 语义，所有执行器必须显式声明 `idempotent`
   （注册时校验，缺失即报错）；有外部副作用且 `idempotent=True` 的执行器必须实现
   `check_already_done` 先查后写，无法保证幂等时必须声明 `idempotent=False` 并在
   docstring 标注风险。
2. **状态流转归属**：业务规则（是否重试 / 是否终态 / 是否可取消 / 是否可重试）在
   `domain/execution.py`，流程编排在 `application/task_execution.py`（任务池执行）
   与 `application/task.py`（人工取消 / 重试），`repositories/task.py` 只保留
   行锁、状态持久化与归档等 SQL 原语。
3. **终态即归档**：`success` / `failed` / `canceled` 在写入终态的同时移入归档表，
   任务池只保留 `pending` / `running`；失败任务重新入队时重试计数清零，
   非失败状态返回 422，任务与归档都不存在返回 404。
4. **Celery 任务统一收敛**：新增任务放在 `infrastructure/tasks/`，通过包
   `__init__.py` 导出并同步 `app/core/celery_app.py` 的 `discover_tasks()`；
   任务名前缀固定为 `app.modules.automation.infrastructure.tasks.`，
   新增任务需同步 `infrastructure/celery.py` 的 `TASK_LABELS`（前端任务清单展示名）。
5. **计划任务只通过代码维护**：不提供计划任务创建 / 删除接口，新增或调整周期统一改
   `infrastructure/beat_schedule.py`（已有计划任务可更新配置、启停、立即执行）。
6. **业务代码不直接写 ORM**：定时任务与执行器通过各业务模块的 repository / application
   访问数据（如订单状态同步查询走 `order/repositories/order.py`），
   不在 automation 内直接拼业务表查询。
7. **依赖方向单向**：API → Application → Domain / Infrastructure → Repository；
   `domain/` 与 `repositories/` 不依赖 `schemas`（DTO），只接收原始字段。
8. **保留期可配置**：清理任务通过 `infrastructure/tasks/retention.py` 读取全局设置，
   非法值回退默认值且最少保留 1 天 —— 归档 / 事件 `automation_task_retention_days`（3 天）、
   订单 `order_retention_days`（7 天）、钱包流水 `wallet_transaction_retention_days`（7 天）、
   通知记录 `notification_retention_days`（30 天）。
9. **不改变对外契约**：路由路径、响应模型、字段名与路由函数名（决定 OpenAPI `operationId`）
   变更需明确评审，前端客户端由 `scripts/generate-client.sh` 从 OpenAPI 生成。
10. **数据库迁移**：模块内不编写 / 修改 migration 文件，新增表与字段按项目规范另行生成。
11. **验证方式**：任务池、事件、规则改动后运行
    `pytest backend/tests/api/routes/test_automation.py`；
    计划任务接口当前没有自动化测试，改动后请手工验证更新 / 启停 / 立即执行。

## 七、API 路由

所有接口使用 `app/api/deps.py` 的 `require_permission` 声明权限码
（清单见 `app/init_models_data/permissions.py` 的「自动化」与「计划任务」分类），
路径省略统一前缀 `/api/v1`。

| 权限码 | 覆盖接口 |
| --- | --- |
| `schedule:view` | `GET /schedules/`、`GET /schedules/task-options`、`GET /schedules/{id}`、`GET /schedules/tasks/{task_id}/status` |
| `schedule:update` | `PUT /schedules/{id}` |
| `schedule:manage` | `POST /schedules/{id}/toggle`、`POST /schedules/{id}/run` |
| `automation_task:view` | `GET /automation/tasks/`、`GET /automation/tasks/task-options`、`GET /automation/tasks/archive`、`GET /automation/tasks/{id}` |
| `automation_task:create` | `POST /automation/tasks/` |
| `automation_task:manage` | `POST /automation/tasks/{id}/retry`、`POST /automation/tasks/{id}/cancel` |
| `automation_event:view` | `GET /automation/events/` |
| `automation_event:publish` | `POST /automation/events/` |
| `automation_rule:view` | `GET /automation/rules/`、`GET /automation/rules/{id}` |
| `automation_rule:create` | `POST /automation/rules/` |
| `automation_rule:update` | `PUT /automation/rules/{id}`、`POST /automation/rules/{id}/toggle` |
| `automation_rule:delete` | `DELETE /automation/rules/{id}` |

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | /schedules/ | 计划任务列表 |
| GET | /schedules/task-options | 可配置的 Celery 任务列表（前端下拉） |
| GET | /schedules/{id} | 计划任务详情 |
| PUT | /schedules/{id} | 更新计划任务（支持切换 crontab / interval） |
| POST | /schedules/{id}/toggle | 启用 / 停用计划任务 |
| POST | /schedules/{id}/run | 立即执行一次（不影响原计划） |
| GET | /schedules/tasks/{task_id}/status | 查询 Celery 任务执行状态 |
| GET | /automation/tasks/ | 自动化任务列表（可按状态过滤） |
| GET | /automation/tasks/task-options | 已注册 Executor 任务类型列表（前端下拉） |
| GET | /automation/tasks/archive | 自动化任务归档列表（可按状态过滤） |
| POST | /automation/tasks/ | 创建自动化任务 |
| GET | /automation/tasks/{id} | 自动化任务详情（含来源事件类型与规则名称） |
| POST | /automation/tasks/{id}/retry | 失败任务重新进入队列 |
| POST | /automation/tasks/{id}/cancel | 取消待执行任务 |
| GET | /automation/events/ | 自动化事件列表（可按事件类型过滤） |
| POST | /automation/events/ | 手动发布事件并触发规则分发 |
| GET | /automation/rules/ | 自动化规则列表 |
| POST | /automation/rules/ | 创建自动化规则 |
| GET | /automation/rules/{id} | 自动化规则详情 |
| PUT | /automation/rules/{id} | 更新自动化规则 |
| POST | /automation/rules/{id}/toggle | 启用 / 停用自动化规则 |
| DELETE | /automation/rules/{id} | 删除自动化规则 |

## 八、前端入口

- `/automation/tasks` 任务池：任务列表与创建、失败重试、待执行取消、任务详情；
- `/automation/archives` 归档：终态任务列表与详情、失败任务重新入队；
- `/automation/rules` 规则：规则 CRUD 与启停；
- `/automation/events` 事件：事件记录查看与手动发布；
- `/schedules` 计划任务：配置更新、启停、立即执行、执行状态。

## 九、常见扩展操作

### 1. 新增执行器（新任务类型）

在 `infrastructure/executors/` 新建文件并注册，再在 `infrastructure/executors/__init__.py`
中导入（导入即注册）：

```python
from app.modules.automation.infrastructure.executors.base import (
    BaseExecutor,
    register_executor,
)
from app.modules.automation.models import AutomationTask


@register_executor("send_email")
class SendEmailExecutor(BaseExecutor):
    """邮件通知执行器"""

    idempotent = True  # 必须显式声明；有外部副作用时实现 check_already_done

    def execute(self, *, task: AutomationTask) -> None:
        ...
```

注册后 `POST /automation/tasks` 与规则 `action_type` 才能使用该任务类型。

### 2. 创建或修改自动化规则

```http
POST /api/v1/automation/rules
Authorization: Bearer <superuser-token>

{
  "name": "订单支付 → 提交供应商订单",
  "event_type": "order.paid",
  "action_type": "submit_supplier_order",
  "config": {"task_options": {"priority": 0, "max_retry": 5, "delay_seconds": 180}},
  "is_active": true
}
```

项目内置规则由 `app/init_models_data/automation_rules.py` 在 `init_db` 时幂等播种：
`order.paid → submit_supplier_order`、`order.after_sale_applied → apply_supplier_refund`，
两者的 `max_retry` 分别对齐 `ORDER_FULFILL_FAIL_LIMIT` 与 `ORDER_REFUND_APPLY_LIMIT`。

### 3. 发布业务事件

```python
from app.core.event_bus import publish

publish(event_type="order.paid", payload={"order_id": "10001"})
```

当前使用中的事件类型：`order.paid`（订单已付款）、`order.after_sale_applied`（API 订单申请售后）、
`order.fulfillment_failed`（订单履约异常）；新增事件类型请同步更新
`app/core/event_bus.py` 的说明与 `domain/constants.py` 的 `EVENT_TYPE_LABELS`。

### 4. 新增或调整定时任务

1. 在 `infrastructure/tasks/` 下按职责新建文件，用 `@shared_task(name="app.modules.automation.infrastructure.tasks.<name>")`
   定义任务；
2. 在 `infrastructure/tasks/__init__.py` 导出，并加入 `app/core/celery_app.py` 的 `discover_tasks()`；
3. 需要周期触发时，在 `infrastructure/beat_schedule.py` 的 `init_tasks` 中登记任务与调度；
4. 在 `infrastructure/celery.py` 的 `TASK_LABELS` 中补充展示名。
