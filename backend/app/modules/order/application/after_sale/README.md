# 订单模块：售后（After-Sale）应用服务

## 结构说明

本目录集中订单售后相关的应用服务，按售后类型组织。

售后处理弹窗提交的处理备注会写入订单的 `remark` 字段，便于在订单详情中查看。

```
after_sale/
├── __init__.py
├── cancel.py   # 退单：本地取消退款 / 申请上游退单
├── refund.py   # 部分退款 / 上游退单自动退款
└── README.md
```

## 售后类型

| 类型 | 实现 | 说明 |
| --- | --- | --- |
| 部分退款 | `refund.py`：`refund_order` / `refund_to_wallet` | 管理员指定金额退款入账，仅已完成订单可用 |
| 补发 / 重新履约 | 待实现 | 重新触发履约事件并备注 |
| 人工处理 | `application/fulfillment.py`：`update_order_status` / `record_supplier_order_id` | 手动调整订单状态 / 补录供应商订单号 |
| 退单 | `cancel.py`：`cancel_order`（发布 `order.after_sale_applied` 事件）+ automation 执行器 `apply_supplier_refund` 调用 `application/sync.py`：`apply_refund_application` | 本地/自动/手动商品直接本地退款（不校验 `can_refund`）；API 商品由自动化事件触发上游退单申请，`can_refund` 仅约束 API 商品；异常订单可退单 |

## 依赖

- 上游退单申请：`application/sync.py` 的 `apply_refund_application`（由 automation 执行器
  `apply_supplier_refund` 调用，执行器注册于 `modules/automation/infrastructure/executors/order_refund.py`）
- 退单退款领域规则：`domain/refund.py` 的 `calc_refund_amount`
