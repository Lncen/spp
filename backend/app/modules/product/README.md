# product 模块

> 商品域：商品分类与商品管理。商品包含货源、定价、库存、履约、下单参数等关联配置。

## 一、模块定位

- **商品分类**：`category` 子模块，维护分类树、分类图标与商品数量缓存（当前仍为旧式扁平结构，待重构）。
- **商品**：`product` 子模块，维护商品主表及 5 张关联配置表（货源/定价/库存/履约/下单参数），提供分页查询、创建、更新、删除。

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
├── category/                       # 商品分类（旧式扁平结构）
│   ├── api.py
│   ├── models.py
│   ├── schemas.py
│   └── service.py
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

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | /products/ | 商品分页列表（超管，支持分类/状态/来源/类型/关闭/名称筛选） |
| POST | /products/ | 创建商品及其关联配置（超管） |
| GET | /products/{id} | 商品详情（超管） |
| PUT | /products/{id} | 更新商品及其关联配置（超管） |
| DELETE | /products/{id} | 删除商品及其关联配置（超管） |

## 五、关键设计

1. **职责归位**：路由不写业务；编排在 `application/`；数据访问统一在 `repositories/product.py`；
   定价互斥、库存边界、下单参数去重等纯规则收敛在 `domain/validation.py`。
2. **导入兼容**：`models/`、`schemas/` 通过 `__init__.py` 重导出，`app.modules.product.product.models`
   与 `app.modules.product.product.schemas` 的既有导入路径不变，外部模块与测试无需改动。
3. **API 兼容**：路由路径、响应字段、函数名（OpenAPI operationId）与重构前完全一致。
4. **避免 N+1**：列表/详情响应按商品 ID 批量加载关联配置、分类名、图片、供应商名。
