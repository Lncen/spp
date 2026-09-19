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
  - 会话列表项含 `user_name`（客服坐席视角为用户展示名，普通用户视角为对方客服名）与 `user_avatar_url`（客服坐席视角的用户头像 URL，未设置头像时为 `null`）
  - 会话列表项含 `unread_count`（按查看者角色统计对方发来的未读消息数），供前端展示侧边栏未读徽标
- **未读汇总**：会话未读总数由 `repositories.conversation.count_unread_total` 统计（客服坐席全部会话 / 普通用户自己的会话），
  由 `notification` 模块的 `GET /notifications/unread-summary` 聚合返回，其中 `conversation_unread_count` 供主页面侧边栏「会话」角标使用
- `GET/POST /customer-service/conversations/{id}/messages`：消息查询 / 发送
  - `GET` 支持 `limit`（默认 50，最大 200）与 `before`（消息 ID 游标）懒加载：返回该消息之前更早的一页；`count` 始终为会话消息总数，前端据此判断是否还有更早历史
- `POST /customer-service/conversations/{id}/read`：标记对方消息已读
- `PATCH /customer-service/conversations/{id}/status`：客服开关会话，需 `conversation:update`
- `DELETE /customer-service/conversations/{id}`：客服删除会话及其全部消息，需 `conversation:delete`
- `GET /customer-service/online?user_ids=`：客服批量在线状态，需 `conversation:view`

**数据清理**：会话默认保留 7 天，保留天数由全局设置 `conversation_retention_days`
（管理端「全局设置」页可改，最小 1 天）控制；beat 每天凌晨 05:45 执行
`cleanup_conversations`，按批次（每批 500 条）物理删除超期会话及其全部消息。
超期判定以 `last_message_at` 为准（无消息时取 `created_at`），不区分 open / closed。
该定时任务与人工 `DELETE` 接口是两条独立路径：人工删除立即生效且同时影响对方，
定时任务只清理超期数据。

会话与消息接口的权限分两层：

- 路由层：读取需要 `conversation:self_view` 或坐席 `conversation:view`，发送需要
  `conversation:reply`；
- 应用层：发送按参与者判定——**会话参与者（会话本人或接待方客服坐席）持有 `conversation:reply`
  时才能发送**；非参与者连会话都读不到（400 `无权访问该会话`）。

响应码约定：会话与消息接口的"无权限"一律返回 **400**（`无会话访问权限` /
`无权访问该会话` / `无回复会话权限`），
因为前端把 403 视为登录态失效（清 token 跳登录页），不适合用在会话自助能力上；
管理端接口（`conversation:update` / `conversation:delete` / `conversation:view`）
仍返回 403，与全站 `require_permission` 的 API 级权限语义保持一致。

普通用户由内置「普通用户」角色（`init_models_data/roles.py` 的 `user`）默认持有
`conversation:self_view` / `conversation:reply`：注册与后台创建用户时自动分配，
启动播种时给"无任何角色"的历史账号补授。

## 五、重要约定

- **客服坐席**由权限码 `conversation:view` 界定（`domain.constants.CONVERSATION_VIEW_PERMISSION_CODE`）：
  持有该权限的启用用户即为接待方，可查看全部会话、加入会话实时房间；
  以接待方身份发送消息还需要 `conversation:reply`（与普通用户在本人会话中发送使用同一个权限码），
  只有 `conversation:view` 时只能查看与标记已读。未持有人只能访问自己的会话。
  超级管理员由授权规则天然持有全部权限码，因此仍是坐席。
- 消息实时推送与 typing 房间的接收方固定为「会话用户 + 全部启用坐席」，由
  `authorization.list_active_user_ids_with_permission` 统一取数，不再直接按 `is_superuser` 判定。
- `typing` 的参与者校验由 `infrastructure/room_guard.py` 注册的回调完成，该回调是**同步实现**
  （数据库查询 + 权限缓存），由 realtime 侧在线程池中调用；禁止在事件循环内直接调用，
  否则会阻塞整个 Socket.IO 事件循环。
- **已读是会话级语义**：`ConversationMessage.read_at` 是消息上唯一的时间戳，
  任一参与者标记已读即代表该会话中对方发来的消息全部已读，对其他坐席与用户同时生效。
  **不做坐席级未读**（每个坐席各自维护未读需要额外的读状态表，属 schema 变更范围）。
- **「一个用户一条进行中会话」由应用层保证**：会话表没有 `(user_id, status=open)` 唯一约束，
  建会话前先对用户行加排他锁（`repositories.conversation.lock_conversation_owner`）串行化
  「先查后插」，因此该保证只对走应用层的写入生效，绕库直写仍可能产生重复进行中会话。
  新增唯一约束需改 Migration，当前不引入。
- 权限码清单见 `app/init_models_data/permissions.py` 的「会话」分类：
  `conversation:self_view`（用户自助查看）与
  `conversation:view` / `conversation:reply` / `conversation:update` / `conversation:delete`（客服坐席）。
  发送消息统一使用 `conversation:reply`：普通用户在本人会话中发送与坐席回复共用同一权限码，
  由应用层按参与者身份区分。（不存在 `conversation:self_send` 权限码。）
