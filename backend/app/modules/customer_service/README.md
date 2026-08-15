# customer_service 模块

> 客服业务模块：会话 / 消息 / 已读 / 在线状态。实时传输复用 `realtime` 模块，不直接操作 Socket.IO。

## 一、模块定位

- **业务数据在 customer_service**：会话（`Conversation`）、消息（`ConversationMessage`）持久化到 PostgreSQL；
- **实时传输走 realtime**：消息、已读、typing、在线状态均通过 `realtime.publisher` / Socket.IO 推送；
- 一个用户一条进行中会话，管理端（超管）统一接待，可关闭 / 重新打开会话。

核心链路：

```text
用户/管理端 发送消息
    -> customer_service 落库（ConversationMessage）
    -> 实时发布 customer_service.message.created
    -> Redis Pub/Sub -> Socket.IO -> 会话参与者
```

## 二、目录结构

```text
customer_service/
├── api/                    # 接口层：会话 / 消息 / 已读 / 在线状态
├── application/            # 应用服务：会话管理、消息管理、实时发布
├── domain/                 # 领域常量（会话状态、发送方角色）
├── infrastructure/         # 实时会话守卫注册（依赖倒置）
├── models/                 # Conversation、ConversationMessage
├── repositories/           # 数据访问
└── schemas/                # API 数据传输对象
```

## 三、实时事件

| 事件 | 方向 | 说明 |
| --- | --- | --- |
| `customer_service.message.created` | Server → Client | 新消息，携带 MessagePublic 载荷 |
| `customer_service.message.read` | Server → Client | 对方已读会话消息 |
| `customer_service.typing` | 双向 | 输入中状态，服务端校验参与者后转发 |
| `system.connected / disconnected` | Server → Client | 连接状态（在线状态依据） |

客户端无需手动加入房间：消息按「参与者用户房间」路由（用户本人 + 全部启用管理员）。

## 四、接口

- `GET/POST /customer-service/conversations`：会话列表 / 用户获取或创建会话
  - 会话列表项含 `unread_count`（按查看者角色统计对方发来的未读消息数），供前端展示侧边栏未读徽标
- **未读汇总**：会话未读总数由 `repositories.conversation.count_unread_total` 统计（管理端全部会话 / 普通用户自己的会话），
  由 `notification` 模块的 `GET /notifications/unread-summary` 聚合为「系统通知 + 会话」总未读，供主页面侧边栏角标使用
- `GET/POST /customer-service/conversations/{id}/messages`：消息查询 / 发送
  - `GET` 支持 `limit`（默认 50，最大 200）与 `before`（消息 ID 游标）懒加载：返回该消息之前更早的一页；`count` 始终为会话消息总数，前端据此判断是否还有更早历史
- `POST /customer-service/conversations/{id}/read`：标记对方消息已读
- `PATCH /customer-service/conversations/{id}/status`：管理端开关会话
- `GET /customer-service/online?user_ids=`：管理端批量在线状态
