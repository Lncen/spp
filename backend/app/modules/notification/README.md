# notification 模块

> 全系统**统一通知中心**：接收业务事件 -> 按通知规则生成通知 -> 选择渠道 -> 投递 -> 记录结果。

## 一、模块定位

`notification` 是系统唯一的通知出口，而不是某个业务模块的附属功能：

- 业务模块**不直接调用渠道**（不直接 `send_email` / 不写 Webhook），只发布业务事件或调用统一入口；
- 通知中心负责规则匹配、内容渲染、渠道选择、异步投递与结果追踪（含失败重试）；
- 接收人、渠道、模板以**代码级规则注册表**管理，后续可平滑升级为数据库可配置。

核心链路：

```text
业务模块 publish 事件 -> EventBus 落库 AutomationEvent
    -> notification 监听器（listen "*"）
    -> 登记 NotificationEventConsumption（消费状态）
    -> 匹配 NotificationRule -> 生成 Notification + NotificationDelivery（dedupe_key 幂等）
    -> 实时发布 notification.created（realtime 模块，best-effort）
    -> in_app 落库即送达 / email 进入 Celery 复用 SMTP
    -> 记录投递结果（成功 / 失败重试 / 失败终态）
    -> 兜底扫描（每 5 分钟）恢复超时的 pending/sending 投递并重新入队
    -> 消费重试（每 1 分钟）重新消费失败或中断的事件
```

**实时提醒**：站内通知创建并提交后，向接收用户发布 `notification.created`（走 `realtime` 模块的 Redis Pub/Sub + Socket.IO）。实时通道只是提醒，PostgreSQL 中的 `Notification` 才是事实来源；发布失败不影响落库，前端可在打开通知中心时重新拉取。

设计原则：

- **同步段只做规则匹配与落库**，慢渠道调用一律放入 Celery 任务，不阻塞业务事务；
- **通知与投递分离**：`Notification` 表达「给谁、发什么」，`NotificationDelivery` 表达「哪个渠道、发了几次、结果如何」；
- **注册不做导入副作用**：渠道注册在 `infrastructure/channels/registry.py` + `loader.py` 显式完成；规则在 `domain/rules.py` 注册，首次查询时惰性初始化（幂等），不依赖模块导入顺序；
- **投递幂等 + 兜底恢复**：投递任务通过条件更新认领（仅 `pending`/`failed` 可进入 `sending`），并发重投不会重复发送；投递记录落库即唯一事实源，入队失败不阻断接口（仅记日志），由 beat 兜底扫描恢复超时未推进的投递并补投，防止消息丢失导致永不发送；
- **消费可靠（重试 + 幂等）**：EventBus 只保证尽力分发（监听器失败仅记日志，自动化事件补发也不会重跑 EventBus 监听器），因此通知消费自己记录状态：失败 / worker 中断的消费由 `retry_notification_consumptions`（每分钟）按指数退避重试，`dedupe_key` 保证重复消费不产生重复通知；
- **站内通知不走异步**：`in_app` 通知落库即视为送达（投递记录直接 `sent`），只有邮件进入 Celery，避免制造无意义的队列任务。

## 二、目录结构

```text
notification/
├── api/                    # 接口层：查询我的通知、未读数、标记已读
├── application/            # 应用服务：事件消费、查询与已读编排
│   └── realtime_publish.py # 通知创建后实时发布（best-effort）
├── domain/                 # 领域层：渠道/状态常量、通知规则注册表
├── infrastructure/         # 基础设施：渠道实现、Celery 投递与兜底扫描、事件监听
│   └── channels/           # 渠道注册表 + 内置渠道（email / in_app）
├── models/                 # 数据模型：Notification、NotificationDelivery
├── repositories/           # 数据访问
├── schemas/                # API 数据传输对象
└── email-templates/        # 邮件模板（MJML 源 + build HTML，全系统复用）
```

## 三、使用与扩展

### 1. 新增通知场景（业务模块）

业务模块发布事件即可，无需感知通知中心：

```python
from app.core.event_bus import publish as publish_event

publish_event(
    event_type="order.fulfillment_failed",
    payload={"order_no": "...", "remark": "..."},
)
```

### 2. 新增通知规则

在 `domain/rules.py` 的 `register_builtin_rules()` 中注册（事件类型 -> 模板 + 接收人 + 渠道）：

```python
register_rule(
    NotificationRule(
        event_type="product.stock_low",
        rule_id="product_stock_low",
        title_template="库存不足：{{ sku }}",
        content_template="商品 {{ sku }} 库存低于阈值。",
        channels=("in_app", "email"),
        recipients=RecipientsSpec(role=RecipientRole.SUPERUSER),
        email_template="notification_stock_low.html",
    )
)
```

`rule_id` 为规则唯一标识，缺省时回退为 `event_type`；`rule_id` 会写入 `notifications.rule_id` 便于审计与筛选。

### 3. 新增渠道

在 `infrastructure/channels/` 下新建文件并注册（不修改 `__init__.py`）：

```python
@register_channel("dingtalk")
class DingTalkChannel(BaseChannel):
    def send(self, *, delivery, notification, session) -> None:
        ...
```

然后在 `infrastructure/channels/loader.py` 的 `load_channels()` 中导入即可生效。

## 四、API 介绍

所有接口均需登录访问（`CurrentUser`），路由前缀 `/notifications`，由 `api/notifications.py` 提供；
标有**管理端**的接口额外要求权限码（`app/api/deps.py` 的 `require_permission`，清单见
`app/init_models_data/permissions.py` 的「通知管理」分类）：
`GET /notifications/admin` → `notification:view`，`POST /notifications/admin` → `notification:create`，
`POST /notifications/admin/deliveries/{delivery_id}/retry` → `notification:retry`，
`DELETE /notifications/admin/{notification_id}` → `notification:delete`。

### 1. 查询我的通知

`GET /notifications`

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `skip` | int | 0 | 分页偏移 |
| `limit` | int | 50 | 每页条数，范围 1-100 |
| `unread_only` | bool | false | 仅返回未读通知 |

响应 `NotificationsPublic`：

| 字段 | 类型 | 说明 |
|---|---|---|
| `data` | list[NotificationPublic] | 通知列表（最新在前） |
| `count` | int | 当前筛选条件下的通知总数 |
| `unread_count` | int | 当前用户未读通知总数 |

### 2. 查询未读数

`GET /notifications/unread-count`

响应 `UnreadCount`：`unread_count`（当前用户未读通知数）。

主页面侧边栏「通知」角标使用该接口；`notification.created` 实时事件与本地已读 / 删除操作都会触发其刷新。
聊天未读属于 `chat` 模块（`GET /chat/unread-count`），由前端各自组合展示，`notification` 不感知聊天数据。

### 3. 标记单条已读

`POST /notifications/{notification_id}/read`

路径参数 `notification_id`（UUID）。仅可操作本人通知，不存在或非本人时返回 404。

响应 `NotificationPublic`（标记后的通知）。

### 4. 全部标记已读

`POST /notifications/read-all`

将当前用户全部未读通知标记为已读，响应 `Message`：`message`（返回已标记条数文案）。

### 5. 删除我的通知

`DELETE /notifications/{notification_id}`

删除当前登录用户自己的通知记录（级联删除其全部投递记录），不存在或非本人时返回 404。响应 `Message`：`message`。

### 6. 管理端：查询通知记录

`GET /notifications/admin`（`notification:view`）

| 参数 | 类型 | 默认 | 说明 |
|---|---|---|---|
| `skip` | int | 0 | 分页偏移 |
| `limit` | int | 50 | 每页条数，范围 1-100 |
| `event_type` | str \| null | null | 按事件类型筛选 |
| `channel` | str \| null | null | 按渠道筛选（`in_app` / `email`） |
| `status` | str \| null | null | 按投递状态筛选 |
| `keyword` | str \| null | null | 按标题 / 内容模糊搜索 |
| `recipient` | str \| null | null | 按接收人模糊搜索（用户全名 / 用户名 / 邮箱，含无用户记录的 `email_to`） |

响应 `NotificationsAdminPublic`：`data`（一行一条投递记录 `NotificationAdminItem`，含所属通知信息与接收人展示名）、`count`（当前筛选条件下总数）。

### 7. 管理端：手动发送通知

`POST /notifications/admin`（`notification:create`）

请求体 `NotificationSendRequest`：

| 字段 | 类型 | 说明 |
|---|---|---|
| `title` | str | 通知标题（必填） |
| `content` | str | 通知内容 |
| `event_type` | str | 事件类型，默认 `manual` |
| `user_ids` | list[uuid] | 接收用户 ID 列表（非群发时必填，至少一个） |
| `channels` | list[str] | 投递渠道列表（必填，`in_app` / `email`） |
| `broadcast` | bool | 群发标志，默认 `false`；为 `true` 时发送给全部启用用户并忽略 `user_ids` |

为每个接收人生成 `Notification` 与对应渠道的 `NotificationDelivery`，通过 Celery 异步投递；群发（`broadcast=true`）时按「每人一条记录」向全部启用用户写库，已读/删除/未读天然按用户隔离；邮件渠道使用 `notification_manual.html` 模板。响应 `Message`（返回创建的投递条数）。

非群发时 `user_ids` 中存在不存在的用户返回 400，避免静默跳过；群发时没有启用用户返回 400。

### 8. 管理端：重试失败投递

`POST /notifications/admin/deliveries/{delivery_id}/retry`（`notification:retry`）

仅 `failed` 状态的投递可重试：重置为 `pending`、清空错误信息并重新入队。响应 `DeliveryPublic`。

### 9. 管理端：删除通知记录

`DELETE /notifications/admin/{notification_id}`（`notification:delete`）

删除通知实例及其全部投递记录（显式删除，不依赖数据库级联配置）。响应 `Message`。

### 通知对象结构（NotificationPublic）

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | uuid | 通知 ID |
| `title` | str | 通知标题 |
| `content` | str | 通知内容 |
| `event_type` | str | 触发事件类型 |
| `created_at` | datetime | 创建时间 |
| `read_at` | datetime \| null | 已读时间，未读为 null |

`payload_snapshot` 只在服务端内部使用（管理端记录与邮件模板渲染），用户接口与实时推送都不返回，
避免把内部事件载荷暴露给浏览器。

## 五、数据模型

- `notifications`：通知实例（接收人、标题、内容、事件载荷快照、已读时间）。`dedupe_key`（`事件 ID:规则:接收人`）唯一，事件重放 / 重试不会重复通知；手动发送留空，允许重复发送；
- `notification_deliveries`：渠道投递记录（状态机 `pending -> sending -> sent / failed / canceled`，失败自动重试，`attempt_count >= max_attempts` 进入 `failed` 终态），`UNIQUE(notification_id, channel)` 保证一条通知的每个渠道只有一条记录。投递任务以条件更新幂等认领，防止重复发送；超过 `NOTIFICATION_STALE_MINUTES`（默认 30 分钟）仍停留在 `pending`/`sending` 的投递由兜底任务恢复为 `pending` 并重新入队；
- `notification_event_consumptions`：事件消费状态（`pending -> processing -> done / failed`，含 `attempt_count` / `next_retry_at` / `last_error`）。`processing` 超过 15 分钟视为 worker 中断，由重试任务重新认领。
- **数据清理**：通知记录默认保留 30 天，保留天数由全局设置 `notification_retention_days`（管理端「全局设置」页可改，最小 1 天）控制；beat 每天凌晨 03:30 执行 `cleanup_notification_records`，按批次（每批 500 条）物理删除超期通知及其全部投递记录，避免长事务。

## 六、当前内置规则

| 规则标识 | 事件类型 | 接收人 | 渠道 | 邮件模板 |
|---|---|---|---|---|
| `order_fulfillment_failed` | `order.fulfillment_failed`（订单履约异常） | 超管 | in_app + email | `notification_order_failed.html` |

手动发送通知（管理端）使用通用邮件模板 `notification_manual.html`（`{{ project_name }}` / `{{ title }}` / `{{ content }}`）。


## 七、前端入口

- **用户侧通知弹窗**：`frontend/src/components/Notifications/NotificationsDialog.tsx`（列表面板 `NotificationPanel.tsx`，弹窗开关由 `NotificationsProvider.tsx` 管理）
  - 布局：顶部标题行（系统通知 + 全部/未读 计数标签 + 全部已读）+ 通知卡片列表（标题 / 内容 / 类型 / 创建时间 / 删除），整体为 Dialog 弹窗；
  - 入口位于侧边栏「项目 → 通知」（`AppSidebar.tsx` 挂载），与「项目 → 会话」（客服工作台）相互独立，点击打开弹窗；
  - 列表**懒加载**：每页 20 条（`skip`/`limit` 分页），滚动到底部自动加载下一页；顶部计数用轻量请求（`limit=1`）获取，未读视图带 `unread_only=true`；点击单条自动标记已读，支持「全部已读」；
  - 单条支持**删除**（`DELETE /notifications/{id}`，AlertDialog 二次确认），删除后同步更新列表与计数缓存；
  - 侧边栏「通知」项显示未读数角标（取自 `GET /notifications/unread-count`，弹窗关闭时失效缓存，避免频繁请求）。
- **管理端通知记录**：`frontend/src/components/Admin/Notifications/`，路由 `/notifications`（管理端页面，需 `notification:view` 等权限码，含群发通知、失败重试、投递详情）；
- **用户表发送通知**：`frontend/src/components/Admin/Users/` 用户行内操作菜单「发送通知」，向指定单个用户发送（事件类型下拉不含群发）。
