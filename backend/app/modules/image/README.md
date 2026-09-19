# 图片模块（image）

## 目录结构

```
modules/image/
├── api/                  # 接口层：权限校验、参数校验、响应
│   ├── images.py         # 图片接口
│   └── categories.py     # 分类管理接口
├── application/          # 应用服务：业务流程编排
│   ├── image_query.py    # 图片列表/详情
│   ├── image_upload.py   # 上传图片
│   ├── image_update.py   # 更新图片
│   ├── image_delete.py   # 删除图片
│   └── category_manage.py # 分类管理
├── domain/               # 领域规则：图片可见性、头像可用性
├── infrastructure/       # 外部交互：PIL 处理、文件存储
├── models/               # 数据模型：Image、ImageCategory
├── repositories/         # 数据访问
└── schemas/              # 请求/响应模型
```

## 核心规则

- 图片上传要求 `image:upload` 权限（内置 `admin` 角色默认持有），普通用户不持有该权限，因此暂不开放上传。
- 图片分类管理接口（`/image-categories`）要求 `image_category:view` / `create` / `update` / `delete` 权限。
- 系统默认图片：超级管理员上传的图片，对所有用户可见。
- 图片可见范围：持有 `image:view` 可见全部图片；否则图片列表与详情 = 自己上传的图片 + 系统默认图片（超管上传）。
- 修改/删除图片：本人上传的图片始终可改可删；操作他人图片需要 `image:update` / `image:delete`。
- 普通用户设置头像时，可选择自己上传的图片或系统默认头像。
- 图片分类由 `ImageCategory` 表驱动（种子数据：avatar/product/product_detail）。

## 权限码

权限清单位于 `app/init_models_data/permissions.py` 的「图片管理」分类；
纯权限接口用 `app/api/deps.py` 的 `require_permission` 声明依赖，
「持有权限或资源归属本人」的接口在路由层用 `require_permission(...).check(...)` 判定，
权限码在 `api/images.py` 导入期完成校验。

| 权限码 | 作用 |
| --- | --- |
| `image:view` | 查看全部用户上传的图片（不持有则仅本人与系统默认图片） |
| `image:upload` | 上传图片（`POST /images/upload` 的硬性依赖） |
| `image:update` | 修改任意图片的分类（不持有则仅能改本人上传） |
| `image:delete` | 删除任意图片（不持有则仅能删本人上传） |
| `image_category:*` | 图片分类的查看 / 创建 / 修改 / 删除 |

超级管理员为系统级 bypass，因此上述权限码对超管恒为通过。
