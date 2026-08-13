# order 模块

> 订单模块：创建订单条件验证与创建订单，以及订单领域规则（状态、退款计算）。
> 履约/查单的流程编排在 automation 模块，上游 API 能力在 supplier 模块。

## 一、模块定位

`order` 是**订单业务模块**，只负责：

- **创建订单**：条件验证（下单权限、下单开关、商品可售、数量、参数、防重复、余额）、
  计价、扣库存、扣款、落库，并发布 `order.paid` 事件；
- **订单领域规则**：状态枚举与上游状态映射、退款公式与入账、本地取消、状态手动维护；
- **手动履约接口适配**：`/orders/{id}/fulfill`、`/orders/{id}/sync-status` 保持同步语义，
  转发到 automation 的编排服务，API 契约不变。

`order` **不直接访问上游 API**（下单/查单/退单）。上游能力统一由
`supplier.application.upstream_order` 提供，流程编排由 `automation` 承担：

```text
order（验证 + 创建 + 领域规则）──→ supplier（上游能力）
                 │
                 └──→ automation（履约/查单编排）──→ supplier / order 领域规则
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
│   ├── create.py                   # 创建订单：条件验证、计价、扣库存、扣款、落库、发事件
│   ├── fulfillment.py              # 手动履约/查单薄适配（编排在 automation）+ 补录上游单号 + 状态维护
│   ├── order_state.py              # 履约状态转换规则（认领/回滚/转异常/终态/上游状态映射）
│   ├── query.py                    # 订单查询
│   └── after_sale/
│       ├── cancel.py               # 本地取消（未向上游下单的订单）
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
│   ├── order.py                    # 订单快照、防重复、参数展开
│   └── stock.py                    # 库存扣减 / 回补
└── schemas/
    ├── __init__.py
    └── order.py                    # 请求 / 响应 DTO
```

## 三、分层职责

| 层 | 职责 | 本模块内容 |
| --- | --- | --- |
| api | 权限验证、接收请求、参数校验、调用 Application、返回响应 | /orders 全部路由 |
| application | 编排业务流程、控制事务 | 创建订单、手动履约适配、状态转换规则、退款入账 |
| domain | 核心业务规则、领域约束 | 状态枚举、计价、退款公式、下单校验 |
| infrastructure | 外部系统交互 | 通知事件发布（无上游调用） |
| repositories | 数据查询、数据持久化 | 订单快照、防重复、库存、订单参数 |
| models | 数据模型 | Order / OrderParam |
| schemas | 数据传输对象 | 请求 / 响应 DTO |

## 四、与上下游模块的边界

| 关注点 | 所在模块 | 说明 |
| --- | --- | --- |
| 上游下单 / 查单 / 退单能力 | `supplier.application.upstream_order` | 纯能力封装，异常语义透传 |
| 履约编排（认领 → 下单 → 分流） | `automation.application.order_fulfillment` | 同步入口与事件执行器共用 |
| 查单/退单编排 | `automation.application.order_status_sync` | 定时任务与手动接口共用 |
| 履约状态转换规则 | `order.application.order_state` | 认领、回滚、转异常、终态、状态映射 |
| 退款入账规则 | `order.application.after_sale.refund` | 公式与钱包入账 |
| 定时任务 | `automation.infrastructure.tasks` | `sync_order_status_periodic`（任务名不变） |

## 五、关键设计

1. **手动接口同步语义不变**：`/orders/{id}/fulfill` 与 `/orders/{id}/sync-status` 仍同步返回
   `OrderPublic`，前端无需适配；编排统一在 automation，手动入口与事件驱动入口共用同一编排服务。
2. **有意例外**：`application/fulfillment.py` 转发到 automation 编排服务，存在 order → automation
   依赖。这是"同步手动接口"的必然产物，仅限该适配文件，不作为通用依赖方向。
3. **状态机规则归位**：`claim_order`、回滚认领、转异常、终态回写等订单状态转换规则保留在本模块
   （`application/order_state.py`），automation 只做流程编排，不内置订单领域规则。
4. **异常语义**：上游结果未知（超时/断连）由 automation 编排转人工确认，明确失败自动重试，
   防止上游重复下单。
5. **创建链路零改动**：条件验证、防重复、扣库存、扣款、落库、`order.paid` 事件均在 `create.py`，
   与自动化履约链路解耦。
