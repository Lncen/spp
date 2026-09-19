# customer_service 模块

> 客服业务模块：会话 / 消息 / 已读 / 在线状态。实时传输复用 `realtime` 模块，不直接操作 Socket.IO。

## 一、模块定位

- **业务数据在 customer_service**：会话（`Conversation`）、消息（`ConversationMessage`）持久化到 PostgreSQL；
- **实时传输走 realtime**：消息、已读、typing、在线状态均通过 `realtime.publisher` / Socket.IO 推送；
- 一个用户一条进行中会话，客服坐席统一接待，可关闭 / 重新打开会话。

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

客户端无需手动加入房间：消息按「参与者用户房间」路由（用户本人 + 全部启用客服坐席）。

## 四、接口

- `GET/POST /customer-service/conversations`：会话列表 / 用户获取或创建会话
  - 会话列表对客服坐席返回全部会话，对普通用户只返回自己的会话
  - 会话列表项含 `unread_count`（按查看者角色统计对方发来的未读消息数），供前端展示侧边栏未读徽标
- **未读汇总**：会话未读总数由 `repositories.conversation.count_unread_total` 统计（客服坐席全部会话 / 普通用户自己的会话），
  由 `notification` 模块的 `GET /notifications/unread-summary` 聚合返回，其中 `conversation_unread_count` 供主页面侧边栏「会话」角标使用
- `GET/POST /customer-service/conversations/{id}/messages`：消息查询 / 发送
  - `GET` 支持 `limit`（默认 50，最大 200）与 `before`（消息 ID 游标）懒加载：返回该消息之前更早的一页；`count` 始终为会话消息总数，前端据此判断是否还有更早历史
- `POST /customer-service/conversations/{id}/read`：标记对方消息已读
- `PATCH /customer-service/conversations/{id}/status`：客服开关会话，需 `customer_service:update`
- `DELETE /customer-service/conversations/{id}`：客服删除会话及其全部消息，需 `customer_service:delete`
- `GET /customer-service/online?user_ids=`：客服批量在线状态，需 `customer_service:view`

会话与消息接口属于用户自助能力，保持「登录即可」，不在路由层下发权限码。

## 五、重要约定

- **客服坐席**由权限码 `customer_service:view` 界定（`domain.constants.AGENT_PERMISSION_CODE`）：
  持有该权限的启用用户即为接待方，可查看全部会话、以管理端身份回复、加入会话实时房间；
  未持有人只能访问自己的会话。超级管理员由授权规则天然持有全部权限码，因此仍是坐席。
- 消息实时推送与 typing 房间的接收方固定为「会话用户 + 全部启用坐席」，由
  `authorization.list_active_user_ids_with_permission` 统一取数，不再直接按 `is_superuser` 判定。
- 权限码清单见 `app/init_models_data/permissions.py` 的「客服管理」分类。
