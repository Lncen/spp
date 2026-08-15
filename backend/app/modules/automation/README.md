# automation 模块

> 基于 `sqlalchemy-celery-beat` 的计划任务管理，并扩展为「事件 → 规则 → 任务 → 执行器」的**业务自动化引擎底座**。

## 一、模块定位

`automation` 定位为**全局业务自动化引擎**，而不是某个业务模块（如订单）的附属功能：

- **计划任务**：管理 `PeriodicTask`（crontab / interval），支持启停、立即执行、执行状态查询；
- **自动化任务池**：`AutomationTask` 持久化业务任务，由 worker 扫描认领并交给 Executor 执行，失败自动重试；
- **任务归档**：终态任务（成功 / 失败 / 取消）完成即移入 `AutomationTaskArchive` 归档表，任务池只保留待执行与执行中任务；
- **定期清理**：归档与事件数据按全局设置 `automation_task_retention_days`（默认 3 天）保留，到期由定时任务同步物理删除；
  已完成订单数据按 `order_retention_days`（默认 7 天）保留，由 `cleanup_completed_orders` 每天清理；
  钱包流水数据按 `wallet_transaction_retention_days`（默认 7 天）保留，由 `cleanup_wallet_transactions` 每天清理；
- **任务统一收敛**：全项目 Celery 任务统一放在 `infrastructure/tasks/`，任务名统一为 `app.modules.automation.infrastructure.tasks.*`；
  `beat_schedule.py` 初始调度、`infrastructure/celery.py` 的 TASK_LABELS 与 `app/core/celery_app.py` 的任务发现同步维护；
- **事件驱动**：业务模块通过 `app/core/event_bus.py` 发布事件 → 落库 `AutomationEvent` → 按启用的 `AutomationRule` 生成自动化任务。

核心链路：

```text
业务事件 → AutomationRule → AutomationTask → Executor
    ↑                                  ↑
event_bus.publish              Celery Worker
```

原则：**Celery 是执行工具，不承载业务**；业务任务统一落库为 `AutomationTask`，避免「一个订单一个 beat」的失控调度。

## 二、使用方法

### 1. 注册任务执行器（新增任务类型）

执行器是任务池真正干活的组件。在 `infrastructure/executors/` 下新建文件并注册，然后在 `infrastructure/executors/__init__.py` 中导入：

```python
# infrastructure/executors/order_submit.py
import logging

from app.modules.automation.infrastructure.executors.base import (
    BaseExecutor,
    register_executor,
)
from app.modules.automation.models import AutomationTask

logger = logging.getLogger(__name__)


@register_executor("submit_supplier_order")
class SubmitSupplierOrderExecutor(BaseExecutor):
    """提交供应商订单执行器"""

    # 幂等约束：必须显式声明，有外部副作用时必须实现 check_already_done
    idempotent = True

    def execute(self, *, task: AutomationTask) -> None:
        order_id = task.payload["order_id"]
        logger.info("提交供应商订单 order_id=%s", order_id)
        # 业务逻辑；失败时抛出异常，任务池会自动重试
```

```python
# infrastructure/executors/__init__.py
from app.modules.automation.infrastructure.executors import (
    log,  # noqa: F401
    order_submit,  # noqa: F401  新增执行器
)
```

注册后 `POST /automation/tasks` 才能使用该 `task_type`。

内置已注册执行器：`log`（通用占位）、`submit_supplier_order`（订单向上游履约）与
`apply_supplier_refund`（订单向上游申请退单）。
`submit_supplier_order` 的执行体委托 `order.application.fulfillment` 的履约编排服务，
`apply_supplier_refund` 委托 `order.application.sync.apply_refund_application`，
执行器只负责幂等预检查、认领超时兜底与任务终态处理。

#### 执行器幂等约束（强制）

任务池是 **at-least-once 语义**：业务副作用与任务终态不在同一事务，worker 崩溃后任务会被恢复重跑，
因此每个执行器必须显式声明 `idempotent`，未声明时应用/worker 启动注册即报错：

| 类型 | 要求 | 示例 |
| --- | --- | --- |
| 天然幂等（无外部副作用） | 声明 `idempotent = True`，无需钩子 | `log` |
| 外部副作用型 | 声明 `idempotent = True`，必须实现 `check_already_done` 先查后写，并提供重复执行幂等测试 | `submit_supplier_order` |
| 无法保证幂等 | 声明 `idempotent = False`，必须在类 docstring 标注风险 | 暂无 |

`check_already_done` 在 `execute` 之前被任务池调用：返回 `True` 表示业务目标已达成，
任务池直接标记成功并归档，不再调用 `execute`。判定必须基于业务唯一标识（订单号 / 外部单号等）
先查后写，例如订单履约以 `supplier_order_id` 是否已生成为准；并发防重由业务原子操作
（如 `claim_order` 的 `PAID → PROCESSING` 原子更新）兜底。

### 2. 创建自动化任务（一次性执行）

```http
POST /automation/tasks
Authorization: Bearer <superuser-token>

{
  "task_type": "log",
  "payload": {"message": "hello"},
  "priority": 0,
  "execute_at": null,
  "max_retry": 3
}
```

`execute_at` 为空表示立即执行（等待 worker 扫描认领）；`payload` 为执行器所需参数。

### 3. 发布业务事件（业务模块接入）

业务模块在关键节点发布事件，自动化模块按启用规则自动生成任务：

```python
from app.core.event_bus import publish

publish(event_type="order.paid", payload={"order_id": "10001"})
```

前提：存在启用的规则 `AutomationRule(event_type="order.paid", action_type="submit_supplier_order")`。

订单模块已在 `create_order` / `create_admin_order` 成功提交后自动发布 `order.paid`（payload 含 `order_id`），无需额外接入。
API 订单申请售后时由 `cancel_order` 发布 `order.after_sale_applied`（payload 含 `order_id`）。

### 4. 创建自动化规则（事件 → 动作映射）

```http
POST /automation/rules
Authorization: Bearer <superuser-token>

{
  "event_type": "order.paid",
  "action_type": "submit_supplier_order",
  "config": {"task_options": {"priority": 10, "max_retry": 10}},
  "is_active": true
}
```

规则配置 `config` 会合并进任务 payload，且覆盖事件载荷中的同名参数；保留键 `task_options` 不进入 payload，
用于配置任务 `priority`、`max_retry` 与 `delay_seconds`（延时执行秒数，0/缺省立即执行；
订单履约规则 `order.paid` 默认 120 秒，创建订单后延时 2 分钟再提交上游，期间取消订单走本地退款）。

订单履约规则 `order.paid → submit_supplier_order` 与售后退单规则
`order.after_sale_applied → apply_supplier_refund` 已由
`app/init_models_data/automation_rules.py` 在 `init_db` 启动时自动播种（幂等，
`max_retry` 分别对齐 `ORDER_FULFILL_FAIL_LIMIT` 与 `ORDER_REFUND_APPLY_LIMIT`），
无需手工创建；若规则缺失，事件只落库审计、不会生成任务。

### 5. 创建计划任务（周期调度 Celery 任务）

计划任务由 `automation/infrastructure/beat_schedule.py` 的 `init_tasks` 在启动时写入数据库作为初始种子，**不再提供创建 / 删除接口**；周期任务的新增、调整统一通过修改 `beat_schedule.py` 维护。已存在的计划任务支持：

- 更新配置：`PUT /schedules/{id}`（支持切换 crontab / interval）
- 启用 / 停用：`POST /schedules/{id}/toggle`
- 立即执行一次：`POST /schedules/{id}/run`
- 查询执行状态：`GET /schedules/tasks/{task_id}/status`
- 可用任务清单（前端下拉）：`GET /schedules/task-options`

### 6. 任务池执行与重试

- beat 每 3 分钟触发 `automation_task_scan`：恢复失联 running（超过 10 分钟）→ 原子认领到期 pending → 执行 Executor → 成功标记 / 失败重试；
- 失败任务按 `max_retry` 自动重试，重试耗尽进入 `failed` 终态；
- **业务终态即失败**：执行器抛出 `ExecutorTerminalError`（如订单已转人工确认）时跳过重试，任务直接进入 `failed` 终态，不会被误标为成功；
- **终态即归档**：`success` / `failed` / `canceled` 任务完成（或取消）时立即移入归档表 `automation_task_archives`，主表仅保留 `pending` / `running`；
- **失败任务重新进入队列**：`POST /automation/tasks/{id}/retry` 可从任务池或归档表恢复失败任务，重试计数清零并重新获得完整自动重试预算（非失败状态返回 422，任务不存在返回 404）；
- **定期清理**：`cleanup_automation_task_archives` 每天 04:00 执行，先归档遗留终态任务（兜底），再按同一保留期同步物理删除归档与事件中超过保留期的数据；保留天数通过全局设置 `automation_task_retention_days` 配置（`PUT /settings/automation_task_retention_days`，默认 3 天，非法值回退默认）。

## 三、目录结构

```text
backend/app/modules/automation/
├── __init__.py
├── README.md                       # 本文件：模块定位、结构与设计说明
├── api/                            # 接口层：仅路由，不含业务逻辑
│   ├── __init__.py                 # 导出 automation_router、automation_events_router、automation_rules_router、schedule_router、schedule_tasks_router
│   ├── automation.py               # /automation/tasks 任务池管理（列表/创建/详情/重试/取消）
│   ├── events.py                   # /automation/events 事件列表与手动发布
│   ├── rules.py                    # /automation/rules 规则 CRUD 与启停
│   ├── schedules.py                # /schedules 列表/详情/更新、task-options、toggle、run
│   └── tasks.py                    # /schedules/tasks/{task_id}/status
├── application/                    # 应用服务：按业务动作拆分
│   ├── __init__.py
│   ├── schedule_update.py          # 更新计划任务（支持切换 crontab / interval）
│   ├── schedule_toggle.py          # 启用 / 停用计划任务
│   ├── schedule_run.py             # 立即执行一次计划任务
│   ├── schedule_query.py           # 列表 / 详情查询 + PeriodicTask → SchedulePublic
│   ├── task_status.py              # 查询 Celery 任务执行状态
│   ├── task_options.py             # 列出可配置的 Celery 任务
│   ├── executor_options.py         # 列出已注册 Executor（前端任务类型下拉）
│   ├── task_create.py              # 创建自动化任务
│   ├── task_query.py               # 自动化任务列表 / 详情查询
│   ├── archive_query.py            # 自动化任务归档列表查询
│   ├── task_retry.py               # 手动重试失败任务
│   ├── task_cancel.py              # 取消待执行任务
│   ├── event_publish.py            # 发布业务事件
│   ├── event_query.py              # 事件列表查询
│   ├── event_dispatch.py           # 按规则为事件生成自动化任务
│   ├── rule_create.py              # 创建规则
│   ├── rule_update.py              # 更新规则
│   ├── rule_toggle.py              # 启用 / 停用规则
│   ├── rule_delete.py              # 删除规则
│   └── rule_query.py               # 规则列表 / 详情查询
├── domain/                         # 领域逻辑：不依赖 Web 框架 / 数据库 / Celery
│   ├── __init__.py
│   ├── constants.py                # AutomationEventStatus、AutomationTaskStatus、ScheduleType、IntervalPeriod 枚举
│   ├── execution.py                # 任务失败重试规则
│   └── validation.py               # crontab / interval 必填配对校验
├── infrastructure/                 # 基础设施：外部系统交互
│   ├── __init__.py
│   ├── celery.py                   # Celery 任务发现、立即执行、状态查询、TASK_LABELS
│   ├── beat_schedule.py            # Celery beat 初始调度配置（init_tasks）
│   ├── event_listeners.py          # 全局事件监听器（@listen("*")，按规则生成任务）
│   ├── executors/                  # 任务执行器（注册机制）
│   │   ├── __init__.py             # 导入内置执行器，导出 EXECUTORS 注册表
│   │   ├── base.py                 # BaseExecutor 基类 + register_executor + get_executor
│   │   └── log.py                  # log 执行器（通用占位）
│   └── tasks/                      # Celery 定时任务（全项目任务统一收敛，按职责拆分）
│       ├── __init__.py             # 统一导出全部任务
│       ├── scan.py                 # automation_task_scan：扫描任务池并执行
│       ├── cleanup.py              # cleanup_automation_task_archives：归档/事件清理
│       ├── order_status.py         # sync_order_status_periodic：订单状态同步
│       ├── order_cleanup.py        # cleanup_completed_orders：已完成订单数据清理
│       ├── wallet_cleanup.py       # cleanup_wallet_transactions：钱包流水数据清理
│       ├── auth_cleanup.py         # cleanup_expired_refresh_tokens：过期刷新令牌清理
│       ├── product_sync.py         # sync_product_status：商品状态同步
│       ├── supplier_sync.py        # sync_upstream_products + dispatch_upstream_products_sync：供应商上游商品同步
│       ├── notification_delivery.py  # deliver_notification / requeue_stale_notification_deliveries：通知投递与兜底扫描
│       ├── notification_cleanup.py # cleanup_notification_records：通知记录清理
│       ├── expired_data.py         # cleanup_expired_data：过期数据/临时文件清理
│       └── wallet_cleanup.py       # cleanup_wallet_transactions：钱包流水数据清理
├── models/                         # 数据模型（SQLModel 表模型）
│   ├── __init__.py
│   ├── task.py                     # AutomationTask（任务池：状态机、优先级、重试、payload、来源事件/规则、认领/开始/完成时间线）
│   ├── archive.py                  # AutomationTaskArchive（终态任务归档：task_id 保留原任务 ID、last_error、时间线、archived_at）
│   ├── event.py                    # AutomationEvent（业务事件：分发状态、分发次数、最近错误、分发时间线）
│   └── rule.py                     # AutomationRule（规则：名称/描述/优先级、事件 → 动作映射）
├── repositories/                   # 数据访问：封装 ORM 操作
│   ├── __init__.py
│   ├── schedule.py                 # PeriodicTask / CrontabSchedule / IntervalSchedule 查询与持久化
│   ├── task.py                     # AutomationTask 创建 / 查询 / 原子认领 / 终态归档 / 失败任务重新入队 / 归档清理
│   ├── event.py                    # AutomationEvent 创建 / 查询 / 清理
│   └── rule.py                     # AutomationRule 创建 / 查询 / 启用规则查询
└── schemas/                        # 数据传输对象
    ├── __init__.py
    ├── schedule.py                 # Schedule*/TaskOption/TaskStatus/RunTask 全部 DTO
    └── automation.py               # 任务 / 事件 / 规则 DTO
```

全局事件总线位于 `app/core/event_bus.py`（业务模块只依赖 core，避免反向依赖 automation）。

## 四、分层职责

| 层 | 职责 | 本模块内容 |
| --- | --- | --- |
| api | 权限验证、接收请求、参数校验、调用 Application、返回响应 | 计划任务、任务池、事件、规则路由 |
| application | 编排业务流程、控制事务 | 计划任务 CRUD / 启停 / 立即执行 / 查询，任务池与规则、事件编排，订单履约/状态同步编排 |
| domain | 核心业务规则、领域约束 | 调度类型枚举、crontab / interval 配对校验、重试规则 |
| infrastructure | 外部系统交互 | Celery 任务发现、发送、状态查询，执行器注册与扫描执行 |
| repositories | 数据查询、数据持久化 | PeriodicTask 等表访问、任务池原子认领、事件与规则存取 |
| models | 数据模型 | AutomationTask / AutomationEvent / AutomationRule 表模型 |
| schemas | 数据传输对象 | 请求 / 响应 DTO |

## 五、API 路由

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | /schedules/ | 计划任务列表（超管） |
| GET | /schedules/task-options | 可配置 Celery 任务列表（超管） |
| GET | /schedules/{id} | 计划任务详情（超管） |
| PUT | /schedules/{id} | 更新计划任务（超管） |
| POST | /schedules/{id}/toggle | 启用 / 停用（超管） |
| POST | /schedules/{id}/run | 立即执行一次（超管） |
| GET | /schedules/tasks/{task_id}/status | 查询 Celery 任务状态（超管） |
| GET | /automation/tasks | 自动化任务列表（超管） |
| POST | /automation/tasks | 创建自动化任务（超管） |
| GET | /automation/tasks/task-options | 已注册 Executor 任务类型列表（超管，前端下拉） |
| GET | /automation/tasks/archive | 自动化任务归档列表（超管，可按状态过滤） |
| GET | /automation/tasks/{id} | 自动化任务详情（超管） |
| POST | /automation/tasks/{id}/retry | 失败任务重新进入队列（任务池或归档恢复，超管） |
| POST | /automation/tasks/{id}/cancel | 取消待执行任务（超管） |
| GET | /automation/events | 自动化事件列表（超管） |
| POST | /automation/events | 手动发布事件并触发规则（超管） |
| GET | /automation/rules | 自动化规则列表（超管） |
| POST | /automation/rules | 创建自动化规则（超管） |
| GET | /automation/rules/{id} | 自动化规则详情（超管） |
| PUT | /automation/rules/{id} | 更新自动化规则（超管） |
| POST | /automation/rules/{id}/toggle | 启用 / 停用规则（超管） |
| DELETE | /automation/rules/{id} | 删除自动化规则（超管） |

## 五-补充、前端管理页面

前端在 `/automation` 提供超管「自动化管理」页，四个子页面独立路由（页面内导航切换，
`/automation` 自动跳转到任务池）：

- `/automation/tasks` **任务池**：自动化任务列表（按状态过滤），支持创建一次性任务、失败任务重试、待执行任务取消、查看任务详情；
- `/automation/archives` **归档**：终态任务归档列表（按状态过滤），支持查看详情、失败任务重新入队；
- `/automation/rules` **规则**：事件 → 动作规则 CRUD 与启停；
- `/automation/events` **事件**：事件落库记录查看与手动发布（触发匹配规则）；

计划任务仍由独立的 `/schedules` 页面管理；前端客户端由 `scripts/generate-client.sh` 从 OpenAPI 重新生成；任务类型下拉数据来自
`GET /automation/tasks/task-options`（已注册 Executor 清单）。

## 六、关键设计

1. **职责归位**：业务动作按文件拆分在 `application/`；Celery 交互（`discover_tasks`、`celery_app.tasks`、`AsyncResult`、`send_task`）在 `infrastructure/celery.py`，beat 初始配置在 `infrastructure/beat_schedule.py`；表操作与孤儿调度清理在 `repositories/schedule.py`；枚举与配对约束在 `domain/`。
2. **依赖方向**：API → Application → Domain / Infrastructure → Repository，保持单向。
3. **对外接口不变**：原 schedules 路由路径、响应模型、字段名与重构前一致；新增 /automation/tasks 管理面。
4. **任务池执行链路**：beat 每 3 分钟触发 `automation_task_scan`，先恢复失联的 running 任务（超过 10 分钟未推进视为 worker 崩溃），再以 `UPDATE ... RETURNING` 原子认领到期 pending 任务（多 worker 并发只返回本事务真正认领的行，杜绝重复执行）→ Executor 执行 → 成功标记 / 失败按 `max_retry` 回退重试或进入 failed；业务终态（`ExecutorTerminalError`）跳过重试直接失败归档。
5. **新增表需迁移**：`automation_tasks` 为新增表，迁移文件按项目规范另行生成。
6. **事件驱动链路**：业务模块 `event_bus.publish` 落库事件 → 自动化监听器按启用规则生成任务 → 任务池执行；payload 合并规则为 `事件载荷 + 规则配置（配置优先）`。
7. **终态即归档**：`mark_success` / `mark_failed`（重试耗尽或业务终态）/ `cancel_task` 在同一事务内将任务移入 `automation_task_archives`（原任务 ID 存入 `task_id`，追加 `archived_at`），主表保持精简；失败任务可经 `retry` 接口从归档恢复重新入队（重试计数清零）。
8. **保留期可配置**：保留天数由全局设置 `automation_task_retention_days` 控制（默认 3 天），每天 04:00 的 `cleanup_automation_task_archives` 批量归档遗留终态任务，并同步物理清理超期归档与事件数据。
9. **钱包流水清理**：保留天数由全局设置 `wallet_transaction_retention_days` 控制（默认 7 天，`PUT /settings/wallet_transaction_retention_days` 可调），每天 04:30 的 `cleanup_wallet_transactions` 按 `created_at` 分批物理删除超期流水（`repositories/wallet.py` 的 `purge_old_transactions`），只清流水、不动 `Wallet` 余额表。
10. **执行器幂等强制**：任务池为 at-least-once 语义，所有执行器必须显式声明 `idempotent`（注册时校验），外部副作用型执行器必须实现 `check_already_done` 预执行判定（业务目标已达成则直接成功归档），崩溃重跑不会重复产生副作用；详见「二、使用方法 1」的幂等约束说明。
11. **业务编排归属**：订单履约与状态同步的流程编排在 order 模块（`application/fulfillment.py`、`application/sync.py`）；automation 只负责调度触发——执行器 `submit_supplier_order` 调用履约编排，`sync_order_status_periodic` 定时任务调用状态同步编排。订单状态转换规则保留在 order 模块，上游调用走 supplier 能力服务（`supplier.application.upstream_order`）；全部定时任务文件与任务名统一收敛至 `automation.infrastructure.tasks`，业务模块不再维护 Celery 任务文件。

## 七、演进方向（未实现）

以下功能属于全局自动化引擎的规划方向，尚未实现：

- 具体业务 Executor：如 `sync_product_stock`、`sync_payment_status`、`send_email` 等；
- 业务模块接入真实事件：如库存预警、支付回调、用户通知等；
- 场景扩展：商品自动上下架、用户通知、财务报表、数据维护等。

