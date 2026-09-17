# 本项目

## 前端

* 本项目页面组件使用 `shadcn/ui`。
* 页面滚动条使用透明背景。
* 注意 API 接口触发时机，避免频繁或重复请求。
* `frontend/src/components/ui` 文件夹禁止修改。

---

# 后端

## 核心分层

业务模块内部建议按照以下职责划分：

```text id="948uge"
module/
├── api/                  # API 层：接口
├── models/               # Model 层：数据模型
├── schemas/              # Schema 层：数据传输对象
├── application/          # Application 层：应用服务
├── domain/               # Domain 层：业务规则
├── infrastructure/       # Infrastructure 层：基础设施
└── repositories/         # Repository 层：数据访问
```

以上目录用于划分职责：

* 不要求每个模块必须包含全部目录。
* 不要求每个业务动作单独创建文件。
* 根据实际职责和复杂度决定是否拆分。

## 分层职责

### API 层

负责：

* 权限验证
* 接收请求
* 参数校验
* 调用 Application 层
* 返回响应

禁止：

* 编写业务逻辑
* 编排复杂业务流程

### Application 层

负责：

* 编排业务流程
* 协调多个领域能力
* 控制事务流程
* 调用 Repository 层
* 调用 Infrastructure 层

例如：

```text id="snu8pn"
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

Application 层负责流程，不负责具体业务规则。

### Domain 层

负责：

* 核心业务规则
* 状态转换
* 业务计算
* 领域约束

例如：

* 价格计算
* 状态机
* 权限规则
* 退款规则

Domain 层不依赖：

* Web 框架
* 数据库
* 第三方 API

### Infrastructure 层

负责：

* 外部系统交互
* 第三方 API
* 消息队列
* 缓存
* 文件存储
* 自动化任务

例如：

```text id="zdq8hr"
供应商接口
支付接口
Redis
Celery
对象存储
```

### Repository 层

负责：

* 数据查询
* 数据持久化
* 数据库访问封装

业务代码避免直接进行大量 ORM 操作。

## 依赖方向

各层依赖应保持单向：

```text id="qgw84g"
API 层
  ↓
Application 层
  ↓
Domain 层
```

```text id="bgg0em"
Application 层
  ├──→ Repository 层
  └──→ Infrastructure 层
```

禁止：

* Domain 层依赖数据库
* Domain 层依赖 Web 框架
* Domain 层直接调用第三方服务
* API 层编写复杂业务逻辑
* Repository 层编排业务流程

## 设计原则

* 不要为了符合目录结构而机械创建文件或目录。
* 新增代码时优先考虑：

  1. 这是业务流程还是业务规则？
  2. 这是内部逻辑还是外部依赖？
  3. 现有文件是否可以合理承载？
  4. 是否确实需要拆分职责？

## 项目约束

### Migration

* 禁止编写或修改数据库 Migration 文件。

### README.md

每个功能模块根目录必须维护 `README.md`，用于说明模块职责与结构。

模块结构或职责发生变化时，应同步更新对应的 `README.md`。

`README.md` 至少应包含：

* **模块定位**：说明模块负责什么、不负责什么。
* **目录结构**：说明当前模块的主要目录及职责。
* **核心职责**：说明模块包含的主要业务能力。
* **关键流程**：说明重要业务流程及主要调用关系。
* **重要约定**：说明该模块特有的业务、技术或使用约束。

README.md 主要用于帮助开发者和 Agent 快速理解模块，内容应与实际代码保持一致，避免记录已经失效的设计或历史实现。
