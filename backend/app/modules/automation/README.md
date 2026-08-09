`automation` 模块建议定位为：

> **自动化流程编排模块（Workflow Orchestration Module）**

它不负责订单业务本身，也不负责供应商接口细节，而负责：

* 管理自动化任务
* 调度执行
* 任务状态流转
* 重试
* 超时恢复
* 执行记录

推荐结构：

```text
automation/

├── models.py              # 数据库模型
├── schemas/             # API数据结构
├── router/              # 管理接口
├── tasks/               # Celery入口
│
├── services/              # 核心业务逻辑
│   ├── task_service.py
│   ├── executor.py
│   ├── claim_service.py
│   └── retry_service.py
│
├── processors/            # 不同任务执行器
│   ├── base.py
│   ├── submit_order.py
│   ├── sync_order.py
│   ├── deliver_goods.py
│
├── enums.py               # 枚举
├── exceptions.py
└── constants.py
```

---

# 一、automation 的核心模型

## 1. AutomationTask

这是核心表。

```python
# automation/models.py

class AutomationTask(Base):

    __tablename__ = "automation_tasks"


    id = Column(
        BigInteger,
        primary_key=True
    )


    # 关联业务对象
    business_type = Column(
        String(50),
        nullable=False
    )


    business_id = Column(
        BigInteger,
        nullable=False
    )


    # 任务类型
    task_type = Column(
        String(50),
        nullable=False
    )


    # 当前状态
    status = Column(
        String(30),
        nullable=False
    )


    # 执行次数
    retry_count = Column(
        Integer,
        default=0
    )


    # 最大重试次数
    max_retry = Column(
        Integer,
        default=5
    )


    # 下次执行时间
    next_run_at = Column(
        DateTime
    )


    # 当前执行者
    worker_id = Column(
        String(100)
    )


    # 锁时间
    locked_at = Column(
        DateTime
    )


    # 最后错误
    last_error = Column(
        Text
    )


    created_at = Column(
        DateTime
    )


    finished_at = Column(
        DateTime
    )
```

---

为什么不用：

```python
order_id
```

而使用：

```python
business_type
business_id
```

？

因为 automation 不应该只服务订单。

未来：

```text
automation

    |
    +---订单自动采购

    +---库存同步

    +---价格同步

    +---退款处理

    +---供应商同步

```

例如：

库存同步：

```json
{
 business_type:"product",
 business_id:100
}
```

---

# 二、任务状态设计

```python
# enums.py

from enum import StrEnum


class TaskStatus(StrEnum):

    PENDING="pending"

    RUNNING="running"

    SUCCESS="success"

    FAILED="failed"

    RETRYING="retrying"

    CANCELLED="cancelled"

```

状态：

```
PENDING

 |
 v

RUNNING

 |
 +--------+
 |        |
 v        v

SUCCESS  FAILED

          |
          v

       RETRYING

          |
          v

       PENDING

```

---

# 三、任务类型

```python
class TaskType(StrEnum):

    SUBMIT_ORDER="submit_order"

    SYNC_ORDER="sync_order"

    DELIVERY="delivery"

    REFUND="refund"

```

---

# 四、创建任务

不要业务代码直接：

```python
AutomationTask(...)
```

统一：

```python
# services/task_service.py


def create_task(
    *,
    db,
    task_type,
    business_type,
    business_id
):

    task = AutomationTask(
        task_type=task_type,
        business_type=business_type,
        business_id=business_id,
        status="pending"
    )


    db.add(task)

    db.commit()

    return task
```

---

订单支付成功：

order模块：

```python
task_service.create_task(
    db=db,
    task_type="submit_order",
    business_type="order",
    business_id=order.id
)
```

---

# 五、Celery入口

tasks.py：

只做入口。

不要写业务。

```python
# automation/tasks.py


@celery.task(
    bind=True,
    max_retries=5
)
def execute_task(
    self,
    task_id
):

    service.execute(task_id)
```

---

真正逻辑：

```python
# services/executor.py


def execute(task_id):

    task = get_task(task_id)


    if not claim(task):
        return


    processor = ProcessorFactory.get(
        task.task_type
    )


    processor.execute(task)


```

---

# 六、Processor设计

## 基类

```python
# processors/base.py


class BaseProcessor:


    def execute(
        self,
        task
    ):
        raise NotImplementedError

```

---

## 提交订单

```python
# processors/submit_order.py


class SubmitOrderProcessor(
    BaseProcessor
):


    def execute(
        self,
        task
    ):


        order = get_order(
            task.business_id
        )


        supplier.create_order(
            order
        )


        finish_task(task)

```

---

## 同步状态

```python
class SyncOrderProcessor(
    BaseProcessor
):


    def execute(self,task):

        order = get_order(
            task.business_id
        )


        result = supplier.query(
            order
        )


        update_order_status(
            result
        )


        finish_task(task)
```

---

# 七、Processor工厂

避免：

```python
if task.type=="xxx"
```

设计：

```python
class ProcessorFactory:


    mapping={

        "submit_order":
            SubmitOrderProcessor,


        "sync_order":
            SyncOrderProcessor,


        "delivery":
            DeliveryProcessor

    }


    @classmethod
    def get(cls,type):

        return cls.mapping[type]()
```

---

# 八、Claim机制放哪里？

你的：

```python
claim_order()
```

应该升级为：

```python
claim_task()
```

原因：

真正需要锁的是任务。

例如：

```text
task 100

submit_order


worker A 抢


worker B 抢失败

```

代码：

```python
def claim_task(task):

    update:

    status=PENDING

    |

    status=RUNNING

    worker_id=current_worker

```

---

# 九、失败重试

Processor异常：

```python
try:

    processor.execute(task)


except Exception as e:

    retry_task(
        task,
        e
    )

```

更新：

```python
task.status="RETRYING"

task.retry_count +=1

task.next_run_at=now+5min
```

---

# 十、定时扫描

Celery Beat：

```python
@celery.task
def scan_tasks():


    tasks = query(
        status="PENDING",
        next_run_at<=now()
    )


    for task in tasks:

        execute_task.delay(
            task.id
        )
```

---

# 十一、router设计

automation 不需要很多接口。

主要用于后台查看。

例如：

```
GET

/admin/automation/tasks


GET

/admin/automation/tasks/{id}


POST

/admin/automation/tasks/{id}/retry


POST

/admin/automation/tasks/{id}/cancel

```

---

schemas：

```python
class TaskResponse(BaseModel):

    id:int

    task_type:str

    status:str

    retry_count:int

    last_error:str|None
```

---

# 十二、最终调用关系

```text

Order模块

支付成功

    |
    |
    v


AutomationService

创建任务


    |
    |
    v


AutomationTask


    |
    |
    v


Celery Beat


    |
    |
    v


execute_task


    |
    |
    v


Processor


    |
    |
    v


Order / Supplier / Inventory


```

