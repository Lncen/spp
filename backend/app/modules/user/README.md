# user 模块

> 用户账号、个人资料与密码管理：注册 / 创建 / 查询 / 更新 / 删除，含内部私有接口。

## 一、模块定位

`user` 模块是系统的账号与身份数据源，提供：

- **用户生命周期**：自助注册、超管创建、个人资料更新、密码修改、删除；
- **权限基础**：`is_superuser` 供全局接口鉴权（见 `app/api/deps.py`）；
- **关联主体**：订单、图片、商品等模块通过 `owner_id` 关联 `user` 表。

## 二、目录结构

```text
backend/app/modules/user/
├── __init__.py                       # 模块说明
├── README.md                         # 本文件：模块定位、结构与设计说明
├── api/                              # 接口层：仅路由与权限验证
│   ├── __init__.py                   # 导出 router / private_router（保持外部 import 不变）
│   ├── users.py                      # /users 公共路由
│   └── private.py                    # /private 内部路由（仅 local 环境注册）
├── application/                      # 应用服务：按业务动作拆分
│   ├── user_create.py                # create_user / register_user / create_user_private
│   ├── user_update.py                # update_user / update_user_me / update_password_me
│   ├── user_query.py                 # 分页查询 / get_user_by_email / get_user_by_username / get_user_by_id
│   └── user_delete.py                # delete_user（含关联 items）/ delete_current_user
├── domain/                           # 领域逻辑
│   └── constants.py                  # 密码长度约束、用户名默认取邮箱规则
├── infrastructure/                   # 基础设施
│   └── emails.py                     # 新账号通知邮件封装
├── models/                           # 数据模型
│   ├── __init__.py                   # 导出 User（app.models.py import 路径不变）
│   └── user.py                       # User 表模型
├── repositories/                     # 数据访问
│   └── user.py                       # 查询 / 新增 / 更新 / 删除（只 flush，不提交）
└── schemas/                          # 数据传输对象
    ├── __init__.py                   # 导出全部 DTO（外部 import 路径不变）
    └── user.py                       # 请求 / 响应 DTO
```

## 三、分层职责

| 层 | 职责 | 本模块内容 |
| --- | --- | --- |
| api | 权限验证、接收请求、返回响应 | /users 与 /private 路由 |
| application | 编排业务流程、控制事务 | 唯一性/密码校验、创建/更新/删除流程、邮件通知、提交事务 |
| domain | 核心业务规则 | 密码长度约束、username 默认规则 |
| infrastructure | 外部系统交互 | 新账号通知邮件 |
| repositories | 数据查询、数据持久化 | user 表增删改查（只 flush） |
| models | 数据模型 | User 表模型 |
| schemas | 数据传输对象 | 请求 / 响应 DTO |

## 四、API 路由

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | /users/ | 获取用户列表：用户名/余额/角色/状态；支持 `search` 按用户名/邮箱/昵称模糊搜索（`user:view`） |
| POST | /users/ | 创建新用户（`user:create`，可选邮件通知） |
| PATCH | /users/me | 更新当前用户个人信息 |
| PATCH | /users/me/password | 修改当前用户密码 |
| GET | /users/me | 获取当前用户信息 |
| DELETE | /users/me | 删除当前用户（需设置 allow_delete_account 开启，超管禁止） |
| POST | /users/signup | 用户自助注册 |
| GET | /users/{user_id} | 获取用户详情（含等级名称，`user:view`） |
| PATCH | /users/{user_id} | 更新用户（`user:update`） |
| DELETE | /users/{user_id} | 删除用户（`user:delete`，禁止删自己） |
| POST | /private/users/ | 内部创建用户（仅 local 环境） |

除上表外，`auth` 模块的 `POST /password-recovery-html-content/{email}`（密码找回邮件 HTML 预览）同样要求 `user:view`。

## 五、关键设计

1. **对外接口不变**：`app.modules.user.models` / `schemas` / `api` 的 import 路径通过包 `__init__.py` 保持兼容；路由函数名、HTTP 状态码与错误消息与重构前完全一致。
2. **事务边界**：repositories 只 `flush`，由 application 统一 `commit` + `refresh`。
3. **依赖方向**：api → application → repositories / domain / infrastructure，禁止反向依赖。
4. **字段权限**：`remark`（备注）仅管理员可修改；`bio`（简介）由用户本人维护；`avatar_id`（头像）关联 `image` 表，用户设置头像时校验图片归属。
5. **列表与详情分离**：`GET /users/` 仅返回列表展示字段（`id`/`username`/`balance`/`is_superuser`/`is_active`，余额联查钱包）；`GET /users/{user_id}` 返回详情（含 `level_name`），要求 `user:view`，编辑页打开时调用。
6. **列表搜索**：`GET /users/` 的 `search` 参数对 `username` / `email` / `full_name` 做大小写不敏感的模糊匹配（`ilike`），命中任一字段即返回，搜索词为空时不生效。
7. **删除账号开关**：`DELETE /users/me` 受系统设置 `allow_delete_account` 控制，默认关闭（返回 403）。
8. **权限声明**：管理端接口统一使用 `app/api/deps.py` 的 `require_permission` 声明权限码，不再使用 `get_current_active_superuser`；权限码清单见 `app/init_models_data/permissions.py`。
9. **下单能力不在用户模型**：用户能否下单由权限模块的权限码 `order:create` 决定，`User` 模型与 `UserCreate` / `UserUpdate` 均不再包含 `can_order` 字段；管理员在「权限」分区对该权限码选择「拒绝」即可收回某用户的下单能力，内置 `user` 角色默认持有它。

## 六、重构记录

2026-08-10：由扁平结构（`api.py` / `models.py` / `schemas.py` / `service.py`）按 DDD Lite 约定拆分至当前分层，行为不变。

| 原文件 | 迁移目标 |
| --- | --- |
| `api.py` | `api/users.py` + `api/private.py`（router / private_router 由 `api/__init__.py` 导出） |
| `models.py` | `models/user.py`（由 `models/__init__.py` 导出） |
| `schemas.py` | `schemas/user.py`（由 `schemas/__init__.py` 导出） |
| `service.py` | `application/user_create.py` + `application/user_update.py` + `application/user_query.py` + `application/user_delete.py` + `repositories/user.py` + `domain/constants.py` + `infrastructure/emails.py` |
