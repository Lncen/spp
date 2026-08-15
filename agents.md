# 前端
- 本项目页面组件使用shadcn-ui库
- 页面滚动条使用透明背景
- 注意api接口触发时机， 避免频繁触发，
- frontend\src\components\ui 此文件夹禁止修改

# 后端
## 核心分层

业务模块内部建议按照以下职责划分：

```

module/

├── api/                  # 接口层
├── models/               # 数据模型
├── schemas/              # 数据传输对象
├── application/          # 应用服务
├── domain/               # 领域逻辑
├── infrastructure/       # 基础设施
└── repositories/         # 数据访问

```


## 分层职责


### API

负责：

- 权限验证
- 接收请求
- 参数校验
- 调用 Application
- 返回响应

禁止：

- 编写业务逻辑


### Application

负责：

- 编排业务流程
- 协调多个领域能力
- 控制事务流程

例如：

```

创建订单：

校验
↓
计算
↓
保存
↓
调用外部服务
↓
通知

```

Application 负责流程，不负责具体规则。


### Domain

负责：

- 核心业务规则
- 状态转换
- 业务计算
- 领域约束

例如：

- 价格计算
- 状态机
- 权限规则
- 退款规则

Domain 不依赖：

- Web 框架
- 数据库
- 第三方 API


### Infrastructure

负责：

- 外部系统交互
- 第三方 API
- 消息队列
- 缓存
- 文件存储
- 自动化任务

例如：

```

供应商接口
支付接口
Redis
Celery
对象存储

```


### Repository

负责：

- 数据查询
- 数据持久化
- 数据库访问封装

业务代码避免直接大量操作 ORM。


---

## Service 使用规范

避免创建大型：

```

service.py

```

不要把所有业务集中在一个 Service 中。


推荐：

按照业务动作拆分：

```

application/

create_xxx.py

update_xxx.py

cancel_xxx.py

process_xxx.py

```


---

## 依赖方向

代码依赖必须保持单向：

```

API

↓

Application

↓

Domain

Application

↓

Infrastructure

```


禁止：

- Domain 依赖数据库
- Domain 依赖 Web 框架
- Domain 直接调用第三方服务


---

## 设计原则

### 避免过度设计

不强制：

- 完整 DDD
- 大量抽象接口
- 复杂领域模型

优先：

- 职责明确

新增代码时优先考虑：

1. 这是业务流程还是业务规则？
2. 这是内部逻辑还是外部依赖？
3. 是否应该拆分职责？
