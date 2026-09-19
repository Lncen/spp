# permission 模块

> 权限定义的唯一来源：分类与权限项由系统初始化脚本写入，管理端只读。

## 一、模块定位

`permission` 负责回答“系统里有哪些权限”：

- 维护 `permission_category`（分组）与 `permission`（权限项）；
- 权限码直接存储在 `permission.code` 上，如 `role:view`，不由分类或动作拼接；
- `permission.action` 是动作类型（`view` / `create` / `update` / `manage`），仅用于分组展示与筛选；
- 对外只提供只读查询接口，统一要求 `permission:view` 权限，运行期不存在任何写接口。

本模块**不负责**角色、用户与权限之间的授予关系（见 `authorization` 模块），
也不负责权限判定与缓存。

## 二、目录结构

```text
permission/
├── api/                # 只读接口：分类、权限列表、权限树
├── application/        # 只读查询应用服务
├── domain/             # 权限动作类型 ActionType
├── models/             # permission_category、permission
├── repositories/       # 只读数据访问
└── schemas/            # 对外 DTO
```

## 三、核心职责

- `domain/catalog.py`：`ActionType` 权限动作类型（`view` / `create` / `update` / `manage`），仅用于分组展示与筛选；
- `api/permissions.py`：`GET /permission-categories`、`GET /permissions`（可按 `action` 过滤）、`GET /permissions/tree`，均要求 `permission:view`；
- `repositories/permission.py`：按分类/ID 查询权限，查询有效权限码集合；
- `app/init_models_data/permissions.py`：以列表维护权限分类与权限项清单（`PERMISSION_CATEGORIES_DATA`），幂等同步到数据库，并导出 `ALL_PERMISSION_CODES` 供权限码导入期校验。

## 四、关键流程

```text
PERMISSION_CATEGORIES_DATA（app/init_models_data/permissions.py 列表）
    ↓ app/init_models_data/permissions.py（幂等 upsert）
permission_category + permission（数据库）
    ↓ 只读接口
管理端权限树 / 角色授权界面
```

新增权限的步骤：

1. 在 `app/init_models_data/permissions.py` 的 `PERMISSION_CATEGORIES_DATA` 对应分类下追加权限项（权限码、动作类型、名称与说明）；
2. 业务接口使用 `require_permission("<新权限码>")` 声明所需权限；
3. 执行初始化脚本 `app/initial_data.py` 把新权限写入数据库。

## 五、重要约定

- 权限定义**只能**由初始化脚本写入，禁止在业务代码中新增或修改权限行；
- 权限码是 `permission.code` 的独立字段：分类与动作类型都不参与拼接，新增权限只需保证 `code` 不重复；
- 权限清单以列表形式维护在 `app/init_models_data/permissions.py`，是分类与权限码的唯一来源；
- 清单中移除的权限不物理删除，只置 `is_active=false`，避免历史授权关系断裂；
- 权限码在导入期校验：`require_permission` 收到未登记的权限码会直接导致应用启动失败；
- 权限清单覆盖全部**管理端**接口：分类按业务模块划分（角色、权限、用户、等级、商品、订单、钱包、供应商、价格模板、通知、客服、自动化、计划任务、系统日志、数据备份、图片、系统设置、系统工具）；授权关系接口使用角色管理分类的 `role:*` 与用户管理分类的 `user:assign_permission`；
- **用户自助接口不做硬性拦截**：`/users/me*`、`/wallets/me*`、`/orders/me*`、`POST /orders/`、`/notifications` 用户侧、`/customer-service` 用户侧、`GET /settings/` 保持「登录即可」，因为普通用户没有角色，加权限码会导致其无法使用自身功能；图片模块的列表 / 详情 / 修改 / 删除属于「持有权限或资源归属本人」，用 `require_permission(code).check(...)` 做能力扩展而非硬拦截；
- 只读接口统一要求 `permission:view`：权限校验使用 `app/api/deps.py` 的 `require_permission`，判定逻辑复用 `authorization` 模块的 `has_permission`；
- `GET /permission-categories` 与 `GET /permissions/tree` 是角色授权界面的数据来源，给非超管角色授予 `role:assign_permission` 时应同时授予 `permission:view`，否则该角色打不开授权界面；
- 按项目规范不提交 Migration 文件；上线前需执行 `alembic revision --autogenerate` 与 `alembic upgrade head`。
