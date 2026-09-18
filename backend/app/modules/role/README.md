# role 模块

> 角色、角色权限、用户角色分配与权限检查。

## 一、模块定位

`role` 负责回答“谁能做什么”：

- 维护 `role`、`role_permission`、`user_role` 三张表；
- 提供角色管理、角色授权、用户角色分配与当前用户权限查询接口；
- 提供权限判定与权限缓存；接口声明权限使用 `app/api/deps.py` 的 `require_permission`。

本模块**不负责**权限定义本身（见 `permission` 模块），领域层也不直接访问数据库或 Redis。

## 二、目录结构

```text
role/
├── api/                # 角色管理与用户角色分配接口
├── application/        # 业务流程：角色管理、用户角色分配、权限检查（缓存编排）
├── domain/             # 纯授权规则：是否放行、能否授予
├── infrastructure/     # 权限缓存（Redis）
├── models/             # role、role_permission、user_role
├── repositories/       # 数据访问：角色、角色权限、用户角色、用户权限码
└── schemas/            # 对外 DTO
```

依赖方向：

```text
业务模块 → app/api/deps.py（require_permission）→ role（权限判定与缓存）→ permission（权限定义，只读）
业务模块 → role → system_log（审计写入）
```

## 三、核心职责

| 接口 | 权限码 | 说明 |
| --- | --- | --- |
| `GET /roles` | `role:view` | 角色分页列表 |
| `POST /roles` | `role:create` | 创建自定义角色（`code` 不传时由服务端生成） |
| `GET /roles/{role_id}` | `role:view` | 角色详情 |
| `PATCH /roles/{role_id}` | `role:update` | 修改角色、启停角色 |
| `DELETE /roles/{role_id}` | `role:delete` | 删除自定义角色，并解除用户角色分配 |
| `GET /roles/{role_id}/permissions` | `role:view` | 角色已持有的权限码 |
| `PUT /roles/{role_id}/permissions` | `role:assign_permission` | 全量设置角色权限 |
| `GET /users/me/permissions` | 登录即可 | 当前用户权限码（含超管标记） |
| `GET /users/{user_id}/roles` | `role:view` | 用户已分配角色 |
| `POST /users/{user_id}/roles` | `role:assign_user` | 为用户分配角色 |
| `DELETE /users/{user_id}/roles/{role_id}` | `role:assign_user` | 移除用户角色 |

## 四、关键流程

权限判定（每个请求）：

```text
require_permission(code)
    ↓ PermissionChecker（app/api/deps.py）
has_permission（application/permission_check.py）
    ↓ 缓存命中直接返回；未命中查库并回填（infrastructure/cache.py）
is_permission_granted（domain/authorization.py）
    ↓ 停用账号拒绝 / 超管 bypass / 权限码集合判定
403 或放行
```

角色授权变更：

```text
校验（角色存在、权限有效、防提权）
    ↓ 覆盖 role_permission
提交事务
    ↓ 失效该角色下所有用户的权限缓存
    ↓ record_audit_log 写入 system_log 审计
```

删除角色：

```text
校验（角色存在、非系统内置）
    ↓ 记录受影响用户与权限快照
    ↓ 删除 role_permission、user_role 与 role（同一事务）
提交事务
    ↓ 失效受影响用户的权限缓存
    ↓ record_audit_log（动作：role.delete）
```

## 五、重要约定

- 权限码必须与 `app/init_models_data/permissions.py` 的权限清单一致；`require_permission` 在导入期校验，拼写错误直接启动失败；
- 超级管理员（`user.is_superuser`）为系统级 bypass，且 `/users/me/permissions` 返回全部有效权限码；
- 防提权：非超管只能授予或分配“权限范围不超过自身”的角色与权限；
- 角色码 `code` 是系统内部字段：创建时可不传，服务端自动生成 `role_<12 位十六进制>`；`RoleUpdate` 不包含 `code`，创建后不可修改；
- 系统内置角色（`is_system=true`）不可停用，仅超管可修改，由 `app/init_models_data/roles.py` 维护；
- 系统内置角色不可删除；删除自定义角色会在同一事务内清理 `role_permission` 与 `user_role`，随后失效受影响用户缓存；
- 缓存键为 `spp:perm:{version}:user:{user_id}`，TTL 由 `PERMISSION_CACHE_TTL_SECONDS` 控制；角色变更主动失效，权限定义变更通过递增版本号整体失效，Redis 不可用时自动回落数据库；
- 审计复用 `system_log` 模块的 `record_audit_log`（动作：`role.create` / `role.update` / `role.delete` / `role.assign_permission` / `user.assign_role` / `user.remove_role`）；
- 按项目规范不提交 Migration 文件；上线前需执行 `alembic revision --autogenerate` 与 `alembic upgrade head` 建表。
