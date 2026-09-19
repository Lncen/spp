# role 模块

> 角色定义：角色叫什么、是否启用、是否为系统内置。

## 一、模块定位

`role` 负责回答“系统里有哪些角色”：

- 维护 `role` 一张表；
- 提供角色 CRUD 接口（列表、详情、创建、修改、删除、启停）。

本模块**不负责**：

- 权限定义（有哪些权限码）→ 见 `permission` 模块；
- 角色授权、用户角色分配、用户直授权限、权限判定与缓存 → 见 `authorization` 模块。

## 二、目录结构

```text
role/
├── api/                # 角色定义接口
├── application/        # 角色管理流程：校验 → 写库 → 提交 → 审计
├── models/             # role
├── repositories/       # 角色数据访问
└── schemas/            # 对外 DTO（含 ORM → DTO 的 to_role_public）
```

依赖方向：

```text
role.application → authorization.application（角色删除 / 停用时的授权清理与缓存失效）
authorization    → role.models、role.repositories、role.schemas（只读角色定义）
业务模块 → app/api/deps.py（require_permission）→ authorization（权限判定与缓存）
role.application → system_log（审计写入）
```

## 三、核心职责

| 接口 | 权限码 | 说明 |
| --- | --- | --- |
| `GET /roles` | `role:view` | 角色分页列表 |
| `POST /roles` | `role:create` | 创建自定义角色（`code` 不传时由服务端生成） |
| `GET /roles/{role_id}` | `role:view` | 角色详情 |
| `PATCH /roles/{role_id}` | `role:update` | 修改角色名称、描述与启停状态 |
| `DELETE /roles/{role_id}` | `role:delete` | 删除自定义角色 |

角色授权相关接口（`GET/PUT /roles/{role_id}/permissions`、`/users/{user_id}/roles`、
`/users/{user_id}/permissions`、`/users/me/permissions`）见 `authorization` 模块。

## 四、关键流程

创建 / 修改角色：

```text
校验（名称、角色码；系统内置角色仅超管可改且不可停用）
    ↓ 写 role
提交事务
    ↓ 停用时失效该角色下用户的权限缓存
    ↓ record_audit_log 写入 system_log 审计
```

删除角色：

```text
校验（角色存在、非系统内置）
    ↓ 记录权限快照
    ↓ authorization.remove_role_grants：删除该角色的 role_permission 与 user_role
    ↓ 删除 role（同一事务）
提交事务
    ↓ 失效受影响用户的权限缓存
    ↓ record_audit_log（动作：删除角色）
```

## 五、重要约定

- 角色码 `code` 是系统内部字段：创建时可不传，服务端自动生成 `role_<12 位十六进制>`；`RoleUpdate` 不包含 `code`，创建后不可修改；
- 系统内置角色（`is_system=true`）不可删除、不可停用，仅超管可修改，由 `app/init_models_data/roles.py` 维护；
- 本模块不直接访问 `role_permission`、`user_role`、`user_permission`，跨模块只调用 `authorization.application` 的公开函数；
- `to_role_public` 是角色 ORM → DTO 的唯一转换入口（定义在 `schemas/`），授权模块返回用户角色列表时复用，避免重复映射；
- 审计复用 `system_log` 模块的 `record_audit_log`；
- 按项目规范不提交 Migration 文件；上线前需执行 `alembic revision --autogenerate` 与 `alembic upgrade head`。
