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
    -> 匹配 NotificationRule -> 生成 Notification + NotificationDelivery
    -> Celery 异步投递（in_app 落库即达 / email 复用 SMTP）
    -> 记录投递结果（成功 / 失败重试 / 失败终态）
```

设计原则：

- **同步段只做规则匹配与落库**，慢渠道调用一律放入 Celery 任务，不阻塞业务事务；
- **通知与投递分离**：`Notification` 表达「给谁、发什么」，`NotificationDelivery` 表达「哪个渠道、发了几次、结果如何」；
- **注册不做 `__init__.py` 副作用**：渠道注册在 `infrastructure/channels/registry.py` + `loader.py` 显式完成，规则注册在 `domain/rules.py` 显式完成。

## 二、目录结构

```text
notification/
├── api/                    # 接口层：查询我的通知、未读数、标记已读
├── application/            # 应用服务：事件消费、查询与已读编排
├── domain/                 # 领域层：渠道/状态常量、通知规则注册表
├── infrastructure/         # 基础设施：渠道实现、Celery 投递、事件监听
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
        title_template="库存不足：{{ sku }}",
        content_template="商品 {{ sku }} 库存低于阈值。",
        channels=("in_app", "email"),
        recipients=RecipientsSpec(role=RecipientRole.SUPERUSER),
        email_template="notification_stock_low.html",
    )
)
```

### 3. 新增渠道

在 `infrastructure/channels/` 下新建文件并注册（不修改 `__init__.py`）：

```python
@register_channel("dingtalk")
class DingTalkChannel(BaseChannel):
    def send(self, *, delivery, notification, session) -> None:
        ...
```

然后在 `infrastructure/channels/loader.py` 的 `load_channels()` 中导入即可生效。

## 四、数据模型

- `notifications`：通知实例（接收人、标题、内容、事件载荷快照、已读时间）；
- `notification_deliveries`：渠道投递记录（状态机 `pending -> sending -> sent / failed / canceled`，失败自动重试，`attempt_count >= max_attempts` 进入 `failed` 终态）。

## 五、当前内置规则

| 事件类型 | 接收人 | 渠道 | 邮件模板 |
|---|---|---|---|
| `order.fulfillment_failed`（订单履约异常） | 超管 | in_app + email | `notification_order_failed.html` |
