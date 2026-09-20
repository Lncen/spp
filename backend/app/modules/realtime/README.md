# realtime 模块

> 实时基础设施：Socket.IO 连接管理、用户身份绑定、实时事件发布与跨进程分发（Redis Pub/Sub）。

## 一、模块定位

`realtime` 是**共享的实时传输层**，不是业务模块：

- 它不决定「这个业务到底是不是一条通知」——该判断属于 `notification`；
- 业务模块统一通过 `realtime.publisher` 发布事件，禁止业务模块直接 `socketio.emit()`；
- 多进程/多实例通过 Redis Pub/Sub 分发，Socket.IO 只负责客户端实时连接。

数据可靠性原则：

```text
PostgreSQL = 事实来源
Redis      = 实时事件传输
Socket.IO  = 客户端实时连接
```

实时推送是 best-effort 提醒，失败不影响业务落库；前端以「收到事件刷新 + 打开页面兜底拉取」处理。

## 二、目录结构

```text
realtime/
├── server.py      # Socket.IO 服务端：连接鉴权、房间命名、Presence 生命周期
├── publisher.py   # 发布入口：向用户/房间发布实时事件（同步 + 异步）
├── auth.py        # 握手鉴权（复用现有 JWT）
├── manager.py     # 进程内连接绑定 + Redis 跨进程 Presence
├── events.py      # 实时通道事件名常量
└── README.md
```

## 三、房间与事件

房间统一三种命名，业务模块通过 `server` 提供的构造函数加入：

| 房间 | 用途 |
| --- | --- |
| `user:{user_id}` | 与该用户强相关的提醒：通知、未读数变化 |
| `chat:{chat_id}` | 单个聊天内的事件：新消息、typing、已读 |
| `presence:{user_id}` | 订阅某个用户在线状态变化的连接 |

实时通道自身只产生两个事件：

| 事件 | 方向 | 说明 |
| --- | --- | --- |
| `presence.heartbeat` | Client → Server | 心跳，续期在线状态 TTL |
| `realtime.presence.changed` | Server → Client | 某个用户在线状态变化，发给 `presence:{user_id}` 订阅者 |

`connect` / `disconnect` 不再广播业务事件；聊天与通知等业务事件名由各自业务模块定义。

## 四、在线状态（Presence）

```text
connect                heartbeat（每 30 秒）      disconnect
   ↓                        ↓                       ↓
SADD + EXPIRE 90s      SADD + EXPIRE 90s      Lua：SREM → SCARD →（0 时）DEL
```

- `realtime:online:{user_id}` 是该用户的在线连接集合（多设备多 sid，跨 worker 共享）；
- TTL 90 秒由心跳续期：worker 崩溃 / 进程被杀后，最长 90 秒自动离线，不需要清理任务；
- 断开连接由 Lua 原子完成 `SREM + SCARD + DEL`，不会残留空 Set（历史上 `EXISTS` 判断空 Set 会让用户长期显示在线）；
- 只有「集合中已无任何 sid」才广播离线；同进程仍有该用户其他连接时不会误判离线。

## 五、发布方式

业务模块在事务提交后调用，同步与异步入口严格分开：

| 场景 | 入口 |
| --- | --- |
| FastAPI 同步路由（线程池）、Celery worker、同步事件监听器 | `publish_to_user` / `publish_to_users` / `publish_to_room` |
| async 路由、Socket.IO 事件处理器 | `publish_to_user_async` / `publish_to_users_async` / `publish_to_room_async` |

```python
from app.modules.realtime.publisher import publish_to_user

publish_to_user(user_id, "notification.created", payload)
```

同步入口使用 `write_only=True` 的 `RedisManager`，只向 Socket.IO 的 Redis 通道写消息，
可在任意线程直接调用，不需要后台事件循环；异步入口使用 `AsyncRedisManager` 并支持批量并发发布。
两种发布器都与各 Web 进程 Socket.IO 服务订阅的通道一致，因此跨进程投递到客户端。

## 六、进程拓扑

- **Web 进程**：Socket.IO 服务持有读写 `AsyncRedisManager`，负责订阅 Redis 并投递到本进程连接；
- **Celery worker / 脚本进程**：首次发布时惰性创建 `write_only=True` 的发布器（只写不订阅），无需启动事件循环；
- 发布消息经 Redis 通道广播，所有 Web 进程的 Socket.IO 服务按用户 room 定向投递。

## 七、部署注意事项

- 生产多 worker（如 `fastapi run --workers 4`）时，Socket.IO 使用 WebSocket 传输需要负载均衡层**粘性会话**（sticky session），否则握手后的帧可能被路由到其他 worker；
- 建议保持 `transports=["websocket"]`，避免 long-polling 带来的粘性会话与代理配置复杂度；
- Redis 故障时实时提醒缺失，但业务数据不受影响，前端通过打开通知中心等操作兜底刷新。

## 八、重要约定

- Socket.IO 事件处理器（`connect` / `disconnect` / 业务事件）运行在主事件循环线程内，**禁止在其中执行同步阻塞调用**（数据库查询、同步 Redis、`run_redis_sync`）；
  业务侧的同步查询必须通过 `starlette.concurrency.run_in_threadpool` 转交线程池执行，否则会阻塞所有连接与请求。
- `run_redis_sync` 在事件循环线程内调用时会立即抛错（由调用方快速降级），避免同步等待自己调度的协程导致事件循环停滞数秒。
