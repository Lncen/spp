# supplier 模块

> 供应商管理：供应商 CRUD、上游余额/商品/分类查询、上游商品异步同步到本地，以及面向
> 各平台（当前仅 `ylsup`）的 API 客户端抽象。

## 一、模块定位

`supplier` 是**供应商主数据与上游接入**模块：

- **供应商主数据**：`Supplier` 表保存平台、API 凭证（响应脱敏）、连接状态、余额等；
- **上游接入抽象**：`SupplierClientBase` + `ClientMeta` 注册表按 `platform` 自动路由到具体平台客户端，
  各平台 client 必须把上游原始 dict 转换为 `schemas/upstream.py` 定义的共享契约，业务层不接触上游字段名；
- **上游订单能力服务**：`application/upstream_order.py` 封装上游下单/查单/退单调用，
  order 与 automation 只消费该能力服务，不直接触碰客户端；异常语义与 client 一致（明确失败 vs 结果未知）；
- **上游商品同步**：`POST /suppliers/{id}/upstream-products/sync` 提交 Celery 任务，
  逐个拉取上游商品详情并创建/更新本地商品（未匹配则创建完整商品，匹配则更新成本价与关闭下单状态；
  售价按成本价 1.5 倍维护：固定价格模式写固定售价，商品系数模式写默认折扣率 1.5）；
- **实时余额**：查询上游账户余额后写回 `Supplier.balance`（保留 7 位小数，不可手动修改）。

核心链路：

```text
API → Application → Domain（映射规则）
        │                ↑
        └──→ Infrastructure（客户端 / Celery）→ Repository
```

## 二、目录结构

```text
backend/app/modules/supplier/
├── __init__.py
├── README.md                       # 本文件：模块定位、结构与设计说明
├── api/                            # 接口层：仅路由，不含业务逻辑
│   ├── __init__.py                 # 导出 router
│   └── suppliers.py                # /suppliers 全部路由
├── application/                    # 应用服务：按业务动作拆分
│   ├── __init__.py
│   ├── create.py                   # 创建供应商
│   ├── update.py                   # 更新供应商（禁止修改 balance）
│   ├── delete.py                   # 删除供应商
│   ├── query.py                    # 列表/详情/平台选项 + app_secret 脱敏转换
│   ├── balance.py                  # 查询上游余额并写回数据库
│   ├── upstream.py                 # 上游商品/分类列表、创建同步任务
│   ├── upstream_order.py           # 上游订单能力服务：下单/查单/退单（无业务规则）
│   └── sync.py                     # 单商品同步编排（创建/更新本地商品）
├── domain/                         # 领域逻辑：纯规则，不依赖 Web / 数据库 / Celery
│   ├── __init__.py
│   ├── constants.py                # PlatformEnum 平台枚举
│   └── mapping.py                  # 上游参数/数量边界 → 本地业务字段映射
├── infrastructure/                 # 基础设施：外部系统交互
│   ├── __init__.py
│   └── clients/                    # 供应商 API 客户端
│       ├── __init__.py             # 导入具体平台 client（触发自动注册）
│       ├── base.py                 # 异常、ClientMeta 注册表、HTTP 传输基类、supplier_client 上下文
│       └── ylsup/                  # ylsup 平台实现（client + 数据转换 adapter）
├── models/                         # 数据模型（SQLModel 表模型）
│   ├── __init__.py
│   └── supplier.py                 # Supplier
├── repositories/                   # 数据访问：封装 ORM 操作
│   ├── __init__.py
│   └── supplier.py                 # Supplier CRUD、余额写回、同步相关多表查询与创建
└── schemas/                        # 数据传输对象
    ├── __init__.py                 # 统一导出（含 PlatformEnum 兼容导出）
    ├── supplier.py                 # 供应商/平台/余额/同步任务 API DTO
    └── upstream.py                 # 上游契约（Summary/Detail/Order/Category）+ 上游列表响应 DTO
```

## 三、分层职责

| 层 | 职责 | 本模块内容 |
| --- | --- | --- |
| api | 权限验证、接收请求、参数校验、调用 Application、返回响应 | /suppliers 全部路由，上游异常映射 502 |
| application | 编排业务流程、控制事务 | 供应商 CRUD、余额刷新、上游查询、上游订单能力、同步编排、任务创建 |
| domain | 核心业务规则、领域约束 | PlatformEnum、上游参数 input_type 61→LINK_EXTRACT 映射、数量边界规范化 |
| infrastructure | 外部系统交互、消息队列 | 平台 API 客户端（httpx）、Celery 任务定义与分发 |
| repositories | 数据查询、数据持久化 | Supplier 与 ProductSupplier/Product/Pricing/Inventory/Fulfillment 等数据访问 |
| models | 数据模型 | Supplier 表模型 |
| schemas | 数据传输对象 | 请求/响应 DTO 与跨层上游契约 |

## 四、API 路由

| 方法 | 路径 | 权限码 | 说明 |
| --- | --- | --- | --- |
| GET | /suppliers/ | `supplier:view` | 供应商列表 |
| GET | /suppliers/platform-options | `supplier:view` | 平台枚举选项（前端下拉） |
| GET | /suppliers/{id} | `supplier:view` | 供应商详情 |
| POST | /suppliers/ | `supplier:create` | 创建供应商 |
| PUT | /suppliers/{id} | `supplier:update` | 更新供应商（不含余额） |
| DELETE | /suppliers/{id} | `supplier:delete` | 删除供应商 |
| GET | /suppliers/{id}/balance | `supplier:view` | 查询并写回上游实时余额 |
| GET | /suppliers/{id}/upstream-products | `supplier:view` | 上游商品列表并标记本地同步状态 |
| GET | /suppliers/{id}/upstream-categories | `supplier:view` | 上游商品分类列表 |
| POST | /suppliers/{id}/upstream-products/sync | `supplier:sync` | 创建上游商品异步同步任务 |
| GET | /suppliers/{id}/upstream-products/sync/{task_id} | `supplier:sync` | 查询同步任务状态 |

权限码清单见 `app/init_models_data/permissions.py` 的「供应商管理」分类，接口统一使用 `app/api/deps.py` 的 `require_permission` 声明。

## 五、关键设计

1. **职责归位**：路由不写业务；同步编排在 `application/sync.py`；数据访问统一在
   `repositories/supplier.py`；平台差异在 `infrastructure/clients/` 内收敛。
2. **依赖方向单向**：API → Application → Domain / Infrastructure → Repository。
3. **上游契约统一**：各平台 client 必须把上游原始数据转为 `schemas/upstream.py` 契约，
   业务层只消费契约类型；订单履约、状态同步通过 `application/upstream_order.py` 能力服务访问，
   不直接复用 `SupplierClientBase`。
4. **客户端自动注册**：`ClientMeta` 元类按 `code` 注册具体平台 client，
   `supplier_client` 上下文管理器按供应商 `platform` 路由并保证退出时关闭连接池。
5. **对外接口不变，任务统一收敛**：API 路径、响应字段与重构前一致；Celery 任务
   `sync_upstream_products` 与分发辅助 `dispatch_upstream_products_sync` 已收敛至
   `automation.infrastructure.tasks.supplier_sync`，任务名统一为
   `app.modules.automation.infrastructure.tasks.sync_upstream_products`。
6. **余额写入约束**：`Supplier.balance` 仅由余额同步接口写回，更新接口显式剔除该字段。
