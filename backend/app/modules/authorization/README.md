# authorization 模块

> 授权关系的唯一归属：回答「谁（角色 / 用户）被授予了哪些权限」。

## 一、模块定位

`authorization` 负责授权关系与权限判定：

- 维护 `role_permission`（角色 → 权限）、`user_role`（用户 → 角色）、`user_permission`（用户 → 权限直授 / 直拒）三张授权关系表；
- 提供角色授权、用户角色分配、用户直授权限（允许 / 拒绝）管理接口；
- 计算用户有效权限并提供权限判定入口 `has_permission`，供 `app/api/deps.py` 的 `require_permission` 使用；
- 维护权限缓存（Redis），并在授权变更后主动失效。

本模块**不负责**：

- 权限定义（有哪些权限码）→ 见 `permission` 模块；
- 角色定义（角色名称、启停、系统内置标记）→ 见 `role` 模块；
- 用户定义（账号、状态、等级）→ 见 `user` 模块。

领域层（`domain/`）不依赖数据库、Web 框架与外部服务。

## 二、目录结构

```text
authorization/
├── api/                # 角色授权、用户角色分配、用户直授权限接口
├── application/        # 流程编排：授权变更、缓存失效、审计；权限判定与缓存编排
├── domain/             # 纯授权规则：是否放行、能否授予
├── infrastructure/     # 权限缓存（Redis，叶子基础设施）
├── models/             # role_permission、user_role、user_permission
├── repositories/       # 授权关系查询与持久化、有效权限计算
└── schemas/            # 对外 DTO
```

## 三、核心职责

| 接口 | 权限码 | 说明 |
| --- | --- | --- |
| `GET /roles/{role_id}/permissions` | `role:view` | 角色已持有的权限码 |
| `PUT /roles/{role_id}/permissions` | `role:assign_permission` | 全量设置角色权限 |
| `GET /users/me/permissions` | 登录即可 | 当前用户有效权限码（含超管标记） |
| `GET /users/{user_id}/roles` | `role:view` | 用户已分配角色 |
| `POST /users/{user_id}/roles` | `role:assign_user` | 为用户分配角色 |
| `DELETE /users/{user_id}/roles/{role_id}` | `role:assign_user` | 移除用户角色 |
| `GET /users/{user_id}/permissions` | `user:view` | 用户直授权限：直接授予（allow）与显式拒绝（deny） |
| `PUT /users/{user_id}/permissions` | `user:assign_permission` | 全量设置用户直授允许 |
| `PUT /users/{user_id}/permissions/deny` | `user:assign_permission` | 全量设置用户直授拒绝 |
| `DELETE /users/{user_id}/permissions/{permission_id}` | `user:assign_permission` | 撤销某权限上的直授记录（允许与拒绝一并清除） |

`domain/authorization.py`：

- `GrantEffect`：授权效果类型（`allow` 直接授予 / `deny` 显式拒绝）；
- `is_permission_granted`：停用账号一律拒绝 → 超管系统级 bypass → 权限码集合判定；
- `can_grant_permission_codes`：非超管的操作范围不能超过自身权限码（防提权与防越权剥夺共用）。

## 四、关键流程

有效权限计算：

```text
用户有效权限 = 角色授予（启用角色 ∩ 有效权限） ∪ 直授允许（allow） − 直授拒绝（deny）
超管 = 全部有效权限码
账号停用 = 一律拒绝（不进入集合判定）
```

权限判定（每个请求）：

```text
require_permission(code)              app/api/deps.py，导入期校验权限码是否登记
    ↓ PermissionChecker
has_permission（application/permission_check.py）
    ↓ 缓存命中直接返回；未命中查库并回填（infrastructure/cache.py）
is_permission_granted（domain/authorization.py）
    ↓
403 或放行
```

授权变更（角色授权 / 用户角色 / 用户直授一致）：

```text
校验（角色与用户存在、权限有效、防提权）
    ↓ 覆盖对应的授权关系表
提交事务
    ↓ 失效受影响用户的权限缓存
    ↓ record_audit_log 写入 system_log 审计
```

角色删除与停用由 `role` 模块发起，本模块提供两个入口：

- `role_grant.remove_role_grants`：删除该角色的 `role_permission` 与 `user_role`，返回受影响用户 ID；
- `role_grant.list_role_user_ids`：仅返回受影响用户 ID（角色停用场景，保留授权关系）。

## 五、重要约定

- 授权关系表只由本模块访问：其他模块需要清理或失效授权时，调用 `application/` 层公开函数，不直接访问 `repositories/`；
- 依赖方向：`authorization → permission / role / user` 的**只读**模型与仓储；`role.application → authorization.application / infrastructure.cache`；禁止 `authorization.application` 反向依赖 `role.application`；
- `infrastructure/cache.py` 是叶子基础设施，禁止引用任何业务模块，以保证角色模块调用缓存失效时不产生循环依赖；
- 拒绝优先：`deny` 会从有效权限中扣除，即使该权限来自角色授予或直授允许；
- **超管不受 deny 约束**：`user.is_superuser` 是系统级 bypass，对超管设置 deny 不产生实际效果（避免出现无人可恢复的锁死）；
- **deny 记录不随角色变动清理**：角色停用、删除、重新分配都不影响 `user_permission` 中的拒绝记录，重新获得该角色后拒绝依然生效；
- 同一权限不会同时存在 allow 与 deny 两种效果：对同一 `(user_id, permission_id)` 而言「最后显式写入的一方生效」，两个全量替换接口会自动覆盖对方的记录；
- 允许对用户当前没有的权限设置 deny（预置式的空转记录），不报错；
- 用户直授权限独立于角色：角色停用时该角色带来的权限失效，直授权限保留；
- 授予与拒绝都做防提权校验，且只校验「提交后的目标权限集合 ⊆ 操作者权限集合」，因此非超管可以移除自己权限范围外的既有授权（与角色授权规则保持一致）；
- 缓存键 `spp:perm:{version}:user:{user_id}`，TTL 由 `PERMISSION_CACHE_TTL_SECONDS` 控制；授权变更主动失效，权限定义变更通过递增版本号整体失效，Redis 不可用时自动回落数据库；
- 审计复用 `system_log` 模块的 `record_audit_log`（动作：`分配权限` / `user.assign_role` / `user.remove_role` / `user.assign_permission` / `user.deny_permission` / `user.remove_permission`）；
- 权限码必须与 `app/init_models_data/permissions.py` 的权限清单一致，未登记会导致应用启动失败；
- 按项目规范不提交 Migration 文件；`user_permission` 表（含 `effect` 字段）上线前需执行 `alembic revision --autogenerate` 与 `alembic upgrade head`；若开发库已存在该表，需先 `DROP TABLE user_permission;` 再 autogenerate，否则生成结果可能缺少建表语句。
