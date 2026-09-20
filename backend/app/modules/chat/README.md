# chat 模块

> 聊天领域模块：私聊 / 群聊的统一模型、消息、已读与实时收发。
> 实时传输复用 `realtime` 模块，`chat` 不直接操作 Socket.IO 连接。

## 一、模块定位

`chat` 负责「聊天事实」：

- 聊天（`Chat`）、成员与已读游标（`ChatParticipant`）、消息（`Message`）；
- 私聊 / 群聊的权限与成员规则，消息发送幂等，未读数推算；
- Socket.IO 聊天事件（订阅、发送、typing、已读）与按事件的限流。

`chat` 不负责：

- 系统重要消息（属于 `notification`）；
- 实时连接的建立、鉴权与在线状态（属于 `realtime`）；
- 文件存储（复用项目现有上传能力，消息只保存文件元数据）。

依赖方向单向：`chat → realtime`，`realtime` 不引用 `chat`。

## 二、目录结构

```text
chat/
├── api/              # 接口层：聊天 / 消息 / 已读 / 成员
├── application/      # 应用服务：access（访问判定）、chat_manage、message_manage、read_manage
├── domain/           # 领域常量（类型 / 状态 / 角色 / 消息类型）与消息顺序规则
├── models/           # Chat、ChatParticipant、Message
├── repositories/     # 数据访问：聊天、成员（含未读聚合）、消息（含游标分页）
├── schemas/          # API 数据传输对象
└── README.md
```

后续阶段在同一模块内补齐 `infrastructure/`（Socket.IO 事件、Presence 订阅与限流）。

## 三、核心模型

### Chat

| 字段 | 说明 |
| --- | --- |
| `type` | `DIRECT` / `GROUP` |
| `status` | `ACTIVE` / `CLOSED` |
| `direct_key` | 私聊唯一键：`较小用户 ID:较大用户 ID`，数据库唯一 |
| `name` | 群聊名称 |
| `last_message_*` | 列表展示用的最后消息冗余（ID / 时间 / 预览） |

私聊的「唯一」是**用户对**口径：`direct_key` 由两个用户 ID 排序后拼接，
因此 A→B 与 B→A 命中同一条会话，换个发起方向不会产生第二条；群聊不限数量。

### ChatParticipant

同时承担成员关系与已读游标，`UNIQUE(chat_id, user_id)`；`last_read_message_id` 只允许向前推进。
角色按聊天类型使用：`DIRECT → MEMBER`、`GROUP → OWNER / MEMBER`。

### Message

`message_type` 为 `TEXT` / `FILE`，文件消息只保存 `file_name` / `file_path`。
`UNIQUE(sender_id, client_message_id)` 保证客户端重试不会产生重复消息。

## 四、重要约定

- **消息顺序是 `(created_at, id)`**：主键为 UUID v4，没有时间顺序，禁止用 `id` 比较消息新旧；
  分页与未读数都基于该组合，已读游标仍只存 `last_read_message_id`（读取时再展开为 `(created_at, id)`）。
- **先落库再实时**：消息先提交 PostgreSQL，提交成功后再发布实时事件；实时失败只影响提醒，
  不影响消息事实，前端可重新拉取历史。
- **`last_message_*` 只能前进**：并发发送时更新条件必须基于 `(created_at, id)`，避免后提交的旧消息覆盖新状态。
- **数据表结构**：模块内不编写 / 修改 migration 文件，建表由项目迁移流程统一处理；
  测试库通过 `tests/conftest.py` 的 `SQLModel.metadata.create_all` 建表。

## 五、接口

| 方法与路径 | 说明 | 权限 |
| --- | --- | --- |
| `GET /chat` | 我参与的聊天列表（含未读数、对方展示名） | `chat:self_view` |
| `GET /chat/unread-count` | 全部聊天未读总数（侧边栏角标） | `chat:self_view` |
| `POST /chat/direct` | 创建或复用与指定用户的私聊 | `chat:create` |
| `POST /chat/group` | 创建群聊（创建者为群主） | `chat:group:create` |
| `GET /chat/{chat_id}` | 聊天详情 | `chat:self_view` |
| `GET /chat/{chat_id}/messages` | 消息分页（`limit` + `before` 游标，`count` 为聊天内总数） | `chat:self_view` |
| `POST /chat/{chat_id}/read` | 推进已读游标（只向前） | `chat:self_view` |
| `GET/POST /chat/{chat_id}/participants` | 查看 / 添加群成员 | `chat:self_view`（服务层再判群主） |
| `DELETE /chat/{chat_id}/participants/{user_id}` | 移除群成员 | `chat:self_view`（服务层再判群主） |
| `DELETE /chat/{chat_id}` | 删除会话（仅自己不可见）：私聊移除自己的成员行，群聊为退出群聊（群主需先转让） | `chat:self_view` |

发送消息不走 HTTP：客户端通过 Socket.IO 的 `chat.message.send` 发送，
服务端先落 PostgreSQL 再广播，实时通道失败不影响消息事实。

## 六、实时事件

客户端 → 服务端：

| 事件 | 载荷 | 说明 |
| --- | --- | --- |
| `chat.subscribe` | `{chat_id}` | 访问权校验后加入 `chat:{id}` 与参与者 `presence:{user_id}` 房间 |
| `chat.unsubscribe` | `{chat_id}` | 离开聊天与 presence 房间 |
| `chat.message.send` | `{chat_id, content, message_type, file_name?, file_path?, client_message_id?}` | 先落库后广播 |
| `chat.typing` | `{chat_id, is_typing}` | 不落库，只发给其他参与者 |
| `chat.read` | `{chat_id, message_id}` | 推进已读游标（只向前） |

服务端 → 客户端：

| 事件 | 房间 | 说明 |
| --- | --- | --- |
| `chat.message.created` | `chat:{chat_id}` | 新消息（MessagePublic 载荷） |
| `chat.message.read` | `chat:{chat_id}` | 某成员已读到哪里 |
| `chat.typing` | 参与者 `user:{id}` | 输入中状态 |
| `chat.unread.updated` | `user:{id}` | 该用户某条聊天的未读数变化 |

每个事件独立限流（`chat.message.send` 20/s、`chat.typing` 10/s、`chat.read` 20/s、
`chat.subscribe` 20/s），超限直接丢弃；Redis 不可用时放行，不让限流组件故障阻断聊天。
Presence 由客户端每 30 秒发送 `presence.heartbeat` 续期（服务端 TTL 90 秒）。

## 七、权限与会话可见性

- **模块动作权限**（`chat:self_view` / `chat:send` / `chat:create` / `chat:group:create` /
  `chat:participant:manage`）由路由层校验；
- **数据级权限**由 `ChatParticipant` 决定：只能访问自己参与的聊天，非参与者返回 400
  （前端把 403 视为登录态失效，不适合表达「看不到这条聊天」）；
- **成员管理**：仅群聊可增删成员，群主（或持有 `chat:participant:manage`）可操作；
- **私聊不可退出**：一对用户只有一条私聊，退出会产生「列表里还在、点开却无权限」的死会话；
  群聊可退出，但群主需先转让。

## 八、前端入口

- `frontend/src/components/Chat/`：聊天弹窗（`ChatDialog` 列表 + `ChatPanel` 消息面板）、
  聊天状态（`ChatProvider`，含在线状态）、实时桥（`RealtimeChatBridge`，事件刷新 + 心跳）；
- 侧边栏「聊天」入口显示未读数角标（`GET /chat/unread-count`）；
- 用户列表行内操作菜单「发起私聊」调用 `POST /chat/direct` 后直接打开该聊天。
