# wallet 模块

> 用户钱包与交易流水：当前用户余额查询、流水查询，以及管理端钱包查询与调账。

## 一、模块定位

`wallet` 模块是系统的资金账户数据源，提供：

- **用户钱包**：每个用户一个钱包，首次查询时自动创建，余额单位为元，精确到小数点后 7 位；
- **交易流水**：充值 / 消费 / 退款 / 调账均写入 `WalletTransaction`，保留变动前后余额与操作人；
- **原子扣款**：余额变更使用带条件的 `UPDATE`（`balance + amount >= 0`），避免并发超扣；
- **关联主体**：订单模块通过 `get_wallet_by_user_id` / `adjust_balance` 完成下单扣款与退款入账。
- **流水定期清理**：`WalletTransaction` 按全局设置 `wallet_transaction_retention_days`（默认 7 天）保留，超过保留期的流水由自动化模块定时任务物理删除（`cleanup_wallet_transactions`，每天 04:30），仅清理流水、不影响 `Wallet` 余额表。

## 二、目录结构

```text
backend/app/modules/wallet/
├── __init__.py                       # 模块说明
├── README.md                         # 本文件：模块定位、结构与设计说明
├── api/                              # 接口层：仅路由与权限验证
│   ├── __init__.py                   # 导出 router（保持外部 import 路径不变）
│   └── wallets.py                    # /wallets 用户与管理端路由
├── application/                      # 应用服务：按业务动作拆分
│   ├── __init__.py
│   ├── wallet_adjust.py              # adjust_balance：原子调账 + 流水写入 + 事务控制
│   └── wallet_query.py               # 钱包/流水分页查询、get_or_create_wallet
├── domain/                           # 领域逻辑
│   ├── __init__.py
│   └── constants.py                  # WalletTxType 交易类型常量
├── models/                           # 数据模型
│   ├── __init__.py                   # 导出 Wallet / WalletTransaction（import 路径不变）
│   └── wallet.py                     # Wallet、WalletTransaction 表模型
├── repositories/                     # 数据访问
│   ├── __init__.py
│   └── wallet.py                     # 查/建钱包、原子余额更新、钱包与流水分页
└── schemas/                          # 数据传输对象
    ├── __init__.py                   # 导出全部 DTO（import 路径不变）
    └── wallet.py                     # 调账请求 / 钱包 / 流水响应 DTO
```

## 三、分层职责

| 层 | 职责 | 本模块内容 |
| --- | --- | --- |
| api | 权限验证、接收请求、返回响应 | /wallets 用户与管理端路由 |
| application | 编排业务流程、控制事务 | 调账流程、钱包自动创建、分页查询编排、提交事务 |
| domain | 核心业务规则、领域约束 | 交易类型常量 |
| repositories | 数据查询、数据持久化 | wallet 表访问、原子余额更新、流水查询 |
| models | 数据模型 | Wallet / WalletTransaction 表模型 |
| schemas | 数据传输对象 | 请求 / 响应 DTO |

## 四、API 路由

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | /wallets/me | 获取当前用户钱包 |
| GET | /wallets/me/transactions | 获取当前用户钱包流水 |
| GET | /wallets/ | 获取全部钱包列表（仅超管） |
| GET | /wallets/user/{user_id} | 按用户获取钱包，不存在则自动创建（仅超管） |
| GET | /wallets/{wallet_id} | 按 ID 获取钱包（仅超管） |
| GET | /wallets/{wallet_id}/transactions | 获取指定钱包流水（仅超管） |
| POST | /wallets/{wallet_id}/adjust | 管理员调账：正数入账、负数扣款（仅超管） |
| PATCH | /wallets/{wallet_id} | 更新钱包启用状态（仅超管） |

## 五、关键设计

1. **对外接口不变**：`app.modules.wallet.models` / `schemas` / `api` 的 import 路径通过包 `__init__.py` 保持兼容；`order` 模块对 `wallet.service` 的引用已更新至 `application` 层。
2. **事务边界**：repositories 只执行原子更新与 `flush`，由 application 统一 `commit` + `refresh`；`adjust_balance` 保留 `commit` 参数供订单流程嵌套使用（`commit=False`）。
3. **原子扣款**：余额变更通过带条件的 `UPDATE` 完成（`balance + amount >= 0`），余额不足时回滚并返回 400，避免并发超扣。
4. **依赖方向**：api → application → repositories / domain，禁止反向依赖。
5. **流水保留期可配置**：保留天数由全局设置 `wallet_transaction_retention_days` 控制（`PUT /settings/wallet_transaction_retention_days`，默认 7 天，非法值回退默认），定时任务位于 `automation` 模块 `infrastructure/tasks/wallet_cleanup.py`，分批物理删除超过保留期的流水。

## 六、重构记录

2026-08-11：由扁平结构（`api.py` / `models.py` / `schemas.py` / `service.py`）按 DDD Lite 约定拆分至当前分层，并新增管理端单钱包查询与钱包流水分页接口，原接口行为不变。

2026-08-15：新增钱包流水定期清理：`repositories/wallet.py` 增加 `purge_old_transactions` 分批物理删除，定时任务与调度注册在 `automation` 模块，保留天数由设置模块 `wallet_transaction_retention_days` 控制（默认 7 天）。

| 原文件 | 迁移目标 |
| --- | --- |
| `api.py` | `api/wallets.py`（router 由 `api/__init__.py` 导出） |
| `models.py` | `models/wallet.py`（由 `models/__init__.py` 导出） |
| `schemas.py` | `schemas/wallet.py`（由 `schemas/__init__.py` 导出） |
| `service.py` | `application/wallet_adjust.py` + `application/wallet_query.py` + `repositories/wallet.py` + `domain/constants.py` |
