# product 模块

> 商品域：商品分类、商品管理、用户商品收藏与用户组合。商品包含货源、定价、库存、履约、下单参数等关联配置。

## 一、模块定位

- **商品分类**：`category` 子模块，维护分类树、分类图标与商品数量缓存（当前仍为旧式扁平结构，待重构）。
- **商品**：`product` 子模块，维护商品主表及 5 张关联配置表（货源/定价/库存/履约/下单参数），提供分页查询、创建、更新、删除。
- **商品收藏**：`favorite` 子模块，维护登录用户与商品的收藏关系，为「收藏 + 组合下单」提供选品数据源。
  只负责收藏关系本身，不负责下单（下单在 `order` 模块）。
- **用户组合**：`combo` 子模块，维护用户保存的一组「商品 + 数量模式」（固定数量 / 随机数量），
  供之后复用下单。组合同样不负责下单，也不保存下单参数（参数在下单时填写）。

核心链路：

```text
API → Application → Domain（校验规则）
                    └→ Repository（数据访问）
```

## 二、目录结构

```text
backend/app/modules/product/
├── __init__.py
├── README.md                       # 本文档：模块定位、结构与设计说明
├── constants.py                    # 商品状态/类型/来源/输入控件/定价规则枚举
├── catalog.py                      # 面向用户的商品展示信息批量拼装（收藏 / 组合共用）
├── category/                       # 商品分类（旧式扁平结构）
│   ├── api.py
│   ├── models.py
│   ├── schemas.py
│   └── service.py
├── combo/                          # 用户组合（旧式扁平结构）
│   ├── __init__.py
│   ├── api.py                      # /product-combos 全部路由
│   ├── models.py                   # ProductCombo / ProductComboItem
│   ├── schemas.py                  # 请求/响应 DTO
│   └── service.py                  # 组合增删改查（含明细整体替换）
├── favorite/                       # 用户商品收藏（旧式扁平结构）
│   ├── __init__.py
│   ├── api.py                      # /product-favorites 全部路由
│   ├── models.py                   # ProductFavorite：user_id + product_id 唯一
│   ├── schemas.py                  # 请求/响应 DTO
│   └── service.py                  # 收藏增删查（幂等）
└── product/                        # 商品（DDD Lite 分层）
    ├── __init__.py
    ├── api/                        # 接口层：仅路由与权限，不含业务逻辑
    │   ├── __init__.py             # 导出 product_router
    │   └── products.py             # /products 全部路由
    ├── application/                # 应用服务：按业务动作拆分
    │   ├── __init__.py
    │   ├── create.py               # 创建商品（默认价模板解析、引用校验、落库、同步分类计数）
    │   ├── update.py               # 更新商品（关联配置部分更新、规则校验、分类计数同步）
    │   ├── delete.py               # 删除商品及其关联配置
    │   └── query.py                # 列表/详情查询 + Product→ProductPublic 响应组装
    ├── domain/                     # 领域逻辑：纯业务规则
    │   ├── __init__.py
    │   └── validation.py           # 定价三选一、库存上下界、下单参数 key 唯一
    ├── models/                     # 数据模型（SQLModel 表模型）
    │   ├── __init__.py             # 重导出，保持 app.modules.product.product.models 兼容
    │   └── product.py              # Product 及 5 张关联配置表
    ├── repositories/               # 数据访问：封装 ORM 操作
    │   ├── __init__.py
    │   └── product.py              # 查询/批量 map/关联配置读写/删除
    └── schemas/                    # 数据传输对象
        ├── __init__.py             # 重导出，保持 app.modules.product.product.schemas 兼容
        └── product.py              # 请求/响应 DTO
```

## 三、分层职责

| 层 | 职责 | 模块内容 |
| --- | --- | --- |
| api | 权限验证、接收请求、参数校验、调用 Application、返回响应 | /products 全部路由 |
| application | 编排业务流程、控制事务 | 创建/更新/删除/查询编排，分类计数同步 |
| domain | 核心业务规则、领域约束 | 定价规则互斥、库存上下界、下单参数 key 唯一 |
| repositories | 数据查询、数据持久化 | 商品及关联配置的查询、批量 map、增删改 |
| models | 数据模型 | Product、ProductSupplier、ProductPricing、ProductInventory、ProductFulfillment、ProductBuyParam |
| schemas | 数据传输对象 | 请求/响应 DTO |

## 四、API 路由

| 方法 | 路径 | 权限码 | 说明 |
| --- | --- | --- | --- |
| GET | /products/ | `product:view` | 商品分页列表（支持分类/状态/来源/类型/关闭/名称筛选） |
| POST | /products/ | `product:create` | 创建商品及其关联配置 |
| GET | /products/{id} | `product:view` | 商品详情 |
| PUT | /products/{id} | `product:update` | 更新商品及其关联配置 |
| DELETE | /products/{id} | `product:delete` | 删除商品及其关联配置 |
| GET | /product-categories/ | `product_category:view` | 商品分类树 |
| POST | /product-categories/ | `product_category:create` | 创建商品分类 |
| GET | /product-categories/{category_id} | `product_category:view` | 商品分类详情 |
| PUT | /product-categories/{category_id} | `product_category:update` | 更新商品分类 |
| DELETE | /product-categories/{category_id} | `product_category:delete` | 删除商品分类（有子分类或商品时拒绝） |
| GET | /product-favorites/me | 仅登录 | 当前用户收藏列表（分页，按收藏时间倒序） |
| POST | /product-favorites/me | 仅登录 | 收藏商品（重复收藏幂等） |
| GET | /product-favorites/me/{product_id} | 仅登录 | 查询当前用户是否已收藏该商品 |
| DELETE | /product-favorites/me/{product_id} | 仅登录 | 取消收藏（未收藏时幂等成功） |
| GET | /product-combos/me | 仅登录 | 当前用户组合列表（含明细数量） |
| POST | /product-combos/me | 仅登录 | 保存组合（名称 + 商品明细） |
| GET | /product-combos/me/{combo_id} | 仅登录 | 组合详情（含商品明细与数量模式） |
| PUT | /product-combos/me/{combo_id} | 仅登录 | 更新组合：名称/备注部分更新，明细传入则整体替换 |
| DELETE | /product-combos/me/{combo_id} | 仅登录 | 删除组合及其明细 |

权限码清单见 `app/init_models_data/permissions.py` 的「商品管理」分类，接口统一使用 `app/api/deps.py` 的 `require_permission` 声明。
收藏与组合是登录账号的自助能力，与 `/orders/me` 一致，仅要求登录态，不额外声明权限码；
商品数据本身仍只通过管理端 `/products`（`product:view`）读取。

## 五、关键设计

1. **职责归位**：路由不写业务；编排在 `application/`；数据访问统一在 `repositories/product.py`；
   定价互斥、库存边界、下单参数去重等纯规则收敛在 `domain/validation.py`。
2. **导入兼容**：`models/`、`schemas/` 通过 `__init__.py` 重导出，`app.modules.product.product.models`
   与 `app.modules.product.product.schemas` 的既有导入路径不变，外部模块与测试无需改动。
3. **API 兼容**：路由路径、响应字段、函数名（OpenAPI operationId）与重构前完全一致。
4. **避免 N+1**：列表/详情响应按商品 ID 批量加载关联配置、分类名、图片、供应商名。
5. **收藏字段最小暴露**：收藏列表只返回商品展示字段（名称、主图、分类、状态、是否关闭下单），
   不下发成本价、供应商 SKU 等内部字段；这些字段目前仅对持有 `product:view` 的管理端开放。
6. **收藏唯一性**：`product_favorite` 对 `(user_id, product_id)` 建唯一约束，并发重复收藏由约束兜底，
   服务层捕获冲突后回滚并复用既有记录，保证幂等。用户或商品删除时收藏级联删除。
7. **组合是下单模板，不是订单**：组合只保存「商品 + 数量模式」，不保存下单参数——
   参数含账号等敏感值，且保存同样的参数会让一键下单立刻撞上「同一商品相同参数订单未完成」的防重复规则，
   因此下单参数始终在下单时填写。下单时前端按组合明细拼 `POST /orders/preview` 与 `POST /orders/`，
   组合模块不新增下单入口。
8. **组合约束**：同一用户下组合名称唯一（并发冲突由唯一约束兜底）；同一组合内商品不能重复；
   明细更新为整体替换，展示顺序取提交顺序（`sort`）；用户删除级联删除组合，
   商品删除级联删除对应明细（组合本身保留，明细可能变为空）。
9. **展示字段统一**：收藏与组合响应都走 `catalog.load_product_displays` 批量拼装，
   只下发名称、主图、分类、状态、是否关闭下单，不下发成本价与供应商 SKU。
10. **数量模式**：明细支持 `QuantityMode` 两种模式，`FIXED`（固定数量，用 `quantity`）
    与 `RANDOM`（随机数量，用 `min_quantity` / `max_quantity`）。字段互斥由请求模型校验（422）
    与表级 `ck_product_combo_item_quantity_mode` 双重约束；`RANDOM` 的数量在下单时由调用方
    在最小/最大之间取值，取到的数量同时用于 `POST /orders/preview` 与 `POST /orders/`，
    数量规则、库存、余额等校验仍由订单模块照常执行。
11. **收藏与组合只存商品引用**：两者都只保存商品 ID（组合额外保存数量模式），
    商品展示信息与下单参数在实际使用时再按商品 ID 读取，避免快照过期。
