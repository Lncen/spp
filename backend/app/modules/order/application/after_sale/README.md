# 订单模块：售后（After-Sale）应用服务

## 结构说明

本目录集中订单售后相关的应用服务，按售后类型组织。

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
| 退单 | `cancel.py`：`cancel_order` + `application/sync.py`：`apply_refund_applications` | 本地订单直接退款；API 订单由 celery 调用上游退单接口 |

## 依赖

- 上游退单申请：`application/sync.py`（celery 定时任务调用供应商 `cancel_order`）
- 退单退款领域规则：`domain/refund.py` 的 `calc_refund_amount`
