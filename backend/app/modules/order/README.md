# order 模块

> 订单模块：创建订单条件验证与创建订单，以及订单领域规则（状态、退款计算）。
> 履约/查单的流程编排在本模块，automation 负责调度触发，上游 API 能力在 supplier 模块。

## 一、模块定位

`order` 是**订单业务模块**，只负责：

- **创建订单**：条件验证（下单权限、下单开关、商品可售、商品上游同步状态、数量、参数、防重复、余额）、
  计价、扣库存、扣款、落库，并发布 `order.paid` 事件；
- **组合下单**：`POST /orders/` 一次提交多个商品（勾选收藏后一起结算），逐单独立创建，
  单张失败不影响其他订单；`POST /orders/preview` 提供下单前结算预览，按调用人等级计价，
  不扣库存、不落库；
- **订单领域规则**：状态枚举与上游状态映射、退款公式与入账、本地取消、状态手动维护；
- **履约/查单编排**：认领 → 上游下单 → 失败分流、批量查单 → 快照更新 → 自动退款，
  `/orders/{id}/fulfill`、`/orders/{id}/sync-status` 与自动化执行器 / 定时任务共用同一套编排。

`order` **不直接访问上游 API**（下单/查单/退单）。上游能力统一由
`supplier.application.upstream_order` 提供，流程编排在本模块，automation 通过
执行器 / 定时任务触发：

```text
order（验证 + 创建 + 领域规则 + 履约/查单编排）──→ supplier（上游能力）
                 ↑
automation（执行器 / 定时任务触发）
```

## 二、目录结构

```text
backend/app/modules/order/
├── __init__.py
├── README.md                       # 本文件：模块定位、结构与设计说明
├── api/
│   └── orders.py                   # /orders 全部路由（响应模型与同步语义不变）
├── application/                    # 应用服务：按业务动作拆分
│   ├── __init__.py
│   ├── create.py                   # 创建订单：条件验证、计价、扣库存、扣款、落库、发事件；组合下单与结算预览
│   ├── fulfillment.py              # 履约编排（认领 → 上游下单 → 分流）+ 手动状态维护
│   ├── sync.py                     # 上游状态同步 / 退单申请服务
│   ├── order_state.py              # 履约状态转换规则（认领/回滚/转异常/终态/上游状态映射）
│   ├── query.py                    # 订单查询（关键字匹配订单 ID / 订单号 / 下单参数 / 用户名）
│   └── after_sale/
│       ├── cancel.py               # 取消订单：本地退款 / 发布售后事件申请上游退单
│       └── refund.py               # 退款入账 / 上游退单自动退款
├── domain/                         # 领域逻辑：纯规则
│   ├── __init__.py
│   ├── constants.py                # 订单状态枚举、可售状态、可同步状态集合
│   ├── pricing.py                  # 计价规则
│   ├── refund.py                   # 退款公式
│   └── validation.py               # 商品可售 / 数量 / 参数校验
├── infrastructure/
│   ├── __init__.py
│   └── notification.py             # 履约异常通知（发布业务事件）
├── models/
│   ├── __init__.py
│   └── order.py                    # Order / OrderParam 表模型
├── repositories/
│   ├── __init__.py
│   ├── order.py                    # 订单快照、防重复、参数展开、终态订单清理
│   └── stock.py                    # 库存扣减 / 回补
└── schemas/
    ├── __init__.py
    └── order.py                    # 请求 / 响应 DTO
```

## 三、分层职责

| 层 | 职责 | 本模块内容 |
| --- | --- | --- |
| api | 权限验证、接收请求、参数校验、调用 Application、返回响应 | /orders 全部路由 |
| application | 编排业务流程、控制事务 | 创建订单、履约/查单编排、状态转换规则、退款入账 |
| domain | 核心业务规则、领域约束 | 状态枚举、计价、退款公式、下单校验 |
| infrastructure | 外部系统交互 | 通知事件发布（无上游调用） |
| repositories | 数据查询、数据持久化 | 订单快照、防重复、库存、订单参数、终态订单清理 |
| models | 数据模型 | Order / OrderParam |
| schemas | 数据传输对象 | 请求 / 响应 DTO |

## 四、与上下游模块的边界

| 关注点 | 所在模块 | 说明 |
| --- | --- | --- |
| 上游下单 / 查单 / 退单能力 | `supplier.application.upstream_order` | 纯能力封装，异常语义透传 |
| 履约编排（认领 → 下单 → 分流） | `order.application.fulfillment` | 同步入口与事件执行器共用 |
| 查单编排/退单申请 | `order.application.sync` | 定时任务、手动接口与自动化执行器共用 |
| 履约状态转换规则 | `order.application.order_state` | 认领、回滚、转异常、终态、状态映射 |
| 退款入账规则 | `order.application.after_sale.refund` | 公式与钱包入账 |
| 定时任务 | `automation.infrastructure.tasks` | `sync_order_status_periodic`（状态同步）、`cleanup_completed_orders`（终态订单清理） |

## 五、关键设计

1. **手动接口同步语义不变**：`/orders/{id}/fulfill` 与 `/orders/{id}/sync-status` 仍同步返回
   `OrderPublic`，前端无需适配；编排在本模块，手动入口与事件驱动入口共用同一编排服务。
2. **依赖方向单向**：automation 执行器 / 定时任务调用本模块编排（automation → order），
   本模块不反向依赖 automation，编排归属与模块边界一致。
3. **状态机规则归位**：`claim_order`、回滚认领、转异常、终态回写等订单状态转换规则保留在本模块
   （`application/order_state.py`），编排层只做流程编排，不内置订单领域规则。
4. **异常语义**：上游结果未知（超时/断连）由编排转人工确认，明确失败自动重试，
   防止上游重复下单；异常订单人工重新履约仍明确失败时保持异常，不回退为已付款。
5. **创建链路零改动**：条件验证、防重复、扣库存、扣款、落库、`order.paid` 事件均在 `create.py`，
   与自动化履约链路解耦。
6. **下单成功后不即时查单**：API 履约下单成功（拿到上游单号）即置为 `PROCESSING`，
   不立即调用上游查单接口；后续状态由 `sync_order_status_periodic` 定时同步
   （与手动 `/orders/{id}/sync-status` 共用同一编排），避免批量下单高峰时
   新单查询延迟或失败导致本地状态停留在 `PENDING`。
7. **下单权限来自权限模块**：用户自助下单 `POST /orders/` 要求权限码 `order:create`
   （400 业务性无权限，文案「暂无下单权限」），管理端免扣款代客下单
   `/orders/admin`、`/orders/admin/preview` 要求权限码 `order:admin_create`；
   权限码与默认授予见 `app/init_models_data/permissions.py` 与 `roles.py`（内置
   `user` 角色默认持有 `order:create`）。订单模块不再读取用户字段判断下单权限。
8. **组合下单复用单商品链路**：一张订单仍只对应一个商品，组合下单只是「一次请求多张订单」，
   因此履约、查单、退款、状态同步无需改动。`POST /orders/preview`（要求 `order:create`）
   与 `POST /orders/admin/preview` 共用 `order.application.create.preview_orders`，
   区别只在调用人（决定等级定价）与权限码。
