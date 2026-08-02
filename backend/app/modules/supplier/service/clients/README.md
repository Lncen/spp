## 使用方法

```python
from decimal import Decimal

from app.modules.supplier.models import Supplier
from app.modules.supplier.service.clients.base import ClientMeta


# 场景一：查询余额
def check_supplier_balance(supplier: Supplier) -> Decimal:
    with ClientMeta.get_client(supplier) as client:
        return client.query_balance()


# 场景二：下单
def place_order(supplier: Supplier, product_id: str, qty: int):
    with ClientMeta.get_client(supplier) as client:
        result = client.create_order(product_id=product_id, quantity=qty)
        order_info = client.query_order([int(result["order_id"])])
        return order_info


# 场景三：批量探测多个供应商连通性
def probe_all_suppliers(suppliers: list[Supplier]):
    results = {}
    for sup in suppliers:
        try:
            with ClientMeta.get_client(sup) as client:
                results[sup.platform] = client.probe()
        except Exception:
            results[sup.platform] = False
    return results
```
