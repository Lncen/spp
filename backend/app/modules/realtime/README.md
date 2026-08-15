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
├── server.py      # Socket.IO 服务端：连接/断开处理、用户房间绑定
├── publisher.py   # 发布入口：向用户/房间发布实时事件（同步 + 异步）
├── auth.py        # 握手鉴权（复用现有 JWT）
├── manager.py     # 进程内在线连接管理
├── events.py      # 实时事件名常量
└── README.md
```

## 三、发布方式

业务模块（如 notification）在事务提交后调用：

```python
from app.modules.realtime.events import RealtimeEvent
from app.modules.realtime.publisher import publish_to_user

publish_to_user(user_id, RealtimeEvent.NOTIFICATION_CREATED, payload)
```

多用户发布使用 `publish_to_users(ids, event, data)`；指定房间使用 `publish_to_room(room, event, data)`。

## 四、进程拓扑

- **Web 进程**：启动时 `init_publisher()` 将发布器绑定到主事件循环与完整 `AsyncRedisManager`（读写）；
- **Celery worker 等无主循环进程**：首次发布时惰性创建 `write_only=True` 的 `AsyncRedisManager` 实例与后台事件循环，只写 Redis 不订阅；
- 发布消息经 Redis 通道广播，所有 Web 进程的 Socket.IO 服务按用户 room 定向投递。

## 五、部署注意事项

- 生产多 worker（如 `fastapi run --workers 4`）时，Socket.IO 使用 WebSocket 传输需要负载均衡层**粘性会话**（sticky session），否则握手后的帧可能被路由到其他 worker；
- 建议保持 `transports=["websocket"]`，避免 long-polling 带来的粘性会话与代理配置复杂度；
- Redis 故障时实时提醒缺失，但业务数据不受影响，前端通过打开通知中心等操作兜底刷新。
