# setting 模块

> 运行时可控的全局设置（key-value 结构）：数据库持久化，Redis 缓存加速，默认值兜底。

## 一、模块定位

`setting` 是全局配置中心，提供登录用户可读、超管可写的 key-value 设置：

- **默认值定义**：`DEFAULT_SETTINGS` 声明所有内置设置的默认值与说明，未落库的设置按默认值返回；
- **数据库持久化**：设置写入 `app_setting` 表，支持任意 JSON 值（bool / str / int / list / dict）；
- **Redis 缓存**：读路径优先命中缓存（`app:settings` hash），缓存缺失懒加载全量设置，Redis 不可用时回落数据库；
- **维护模式**：`maintenance_mode` 由安全中间件读取，开启后除白名单接口外全部返回 503。

设置值读取链路：

```text
Redis 缓存 → 数据库 → 默认值
```

## 二、目录结构

```text
backend/app/modules/setting/
├── __init__.py                       # 模块说明
├── README.md                         # 本文件：模块定位、结构与设计说明
├── api/                              # 接口层：仅路由，不含业务逻辑
│   ├── __init__.py                   # 导出 router（保持外部 import 路径不变）
│   └── settings.py                   # /settings 列表读取与更新
├── application/                      # 应用服务：按业务动作拆分
│   ├── __init__.py
│   ├── setting_query.py              # get_setting / get_setting_items（缓存优先 → 回落 DB → 默认值）
│   └── setting_update.py             # update_setting（upsert + 缓存刷新）
├── domain/                           # 领域逻辑：默认值与常量定义
│   ├── __init__.py
│   └── constants.py                  # SettingType 设置类型枚举、AUTOMATION_TASK_RETENTION_DAYS、DEFAULT_SETTINGS、get_default_setting
├── infrastructure/                   # 基础设施：Redis 缓存读写
│   ├── __init__.py
│   └── cache.py                      # SETTINGS_CACHE_KEY、缓存序列化 / 读取 / 懒加载 / 更新
├── models/                           # 数据模型
│   ├── __init__.py                   # 导出 AppSetting（app/models.py import 路径不变）
│   └── setting.py                    # AppSetting（key / type / value 表模型）
├── repositories/                     # 数据访问：封装 ORM 操作
│   ├── __init__.py
│   └── setting.py                    # get_all_settings / 按 key 查询 / upsert / 默认值兜底
└── schemas/                          # 数据传输对象
    ├── __init__.py                   # 导出 SettingRead / SettingsRead / SettingUpdate
    └── setting.py                    # 设置请求 / 响应 DTO
```

## 三、分层职责

| 层 | 职责 | 本模块内容 |
| --- | --- | --- |
| api | 权限验证、接收请求、参数校验、调用 Application、返回响应 | /settings 列表读取与更新路由 |
| application | 编排业务流程、控制事务 | 设置读取（缓存 → DB → 默认值）、更新（upsert + 提交 + 缓存刷新） |
| domain | 核心业务规则、领域约束 | 设置类型枚举（按模块名区分设置归属）、内置设置默认值与说明 |
| infrastructure | 外部系统交互 | Redis 缓存读写与懒加载 |
| repositories | 数据查询、数据持久化 | app_setting 表访问与 upsert |
| models | 数据模型 | AppSetting 表模型（key / type / value） |
| schemas | 数据传输对象 | 请求 / 响应 DTO |

## 四、API 路由

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | /settings/ | 获取全部设置（需登录） |
| PUT | /settings/{key} | 新增或更新设置项（仅超管） |

## 五、关键设计

1. **读路径三级回落**：Redis 缓存 → 数据库 → 默认值；缓存不可用（`_run_cache_redis` 异常）静默回落，不影响业务。
2. **缓存一致性**：更新设置先落库提交，再刷新 Redis 缓存并重置 TTL；缓存未初始化时先全量懒加载。
3. **默认值兜底**：未落库的内置设置（如 `order_enabled`）按 `DEFAULT_SETTINGS` 返回，保证新增设置无需迁移即可生效。
4. **对外接口不变**：`app.modules.setting.models` / `app.modules.setting.schemas` / `app.modules.setting.api` 的 import 路径通过包 `__init__` 保持兼容；`get_setting` 迁移至 `application/setting_query.py`，外部引用已同步更新。
5. **设置类型**：`type` 字段用 `SettingType` 枚举按模块名标识设置归属（如 `system`、`order`）；已存在的 `app_setting` 表新增该列需生成迁移并回填存量行为 `system`。

## 六、重构记录

2026-08-10：由扁平结构（`api.py` / `models.py` / `schemas.py` / `service.py` / `constants.py`）按 DDD Lite 约定拆分至当前分层，行为不变。

| 原文件 | 迁移目标 |
| --- | --- |
| `api.py` | `api/settings.py`（router 由 `api/__init__.py` 导出） |
| `models.py` | `models/setting.py`（由 `models/__init__.py` 导出） |
| `schemas.py` | `schemas/setting.py`（由 `schemas/__init__.py` 导出） |
| `service.py` | `application/setting_query.py` + `application/setting_update.py` + `infrastructure/cache.py` + `repositories/setting.py` |
| `constants.py` | `domain/constants.py` |
