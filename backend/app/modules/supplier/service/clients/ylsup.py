"""ylsup 平台 API client"""

import hashlib
import time
from decimal import Decimal
from typing import Any

from app.modules.supplier.service.clients.base import (
    SupplierClientBase,
    SupplierClientError,
)


class YlsupClient(SupplierClientBase):
    """ylsup 平台 API 客户端"""

    # 用于自动注册键 模型的 platform 字段枚举类型里必须要有值
    code = "ylsup"

    def _sign(self, path: str) -> tuple[str, int]:
        """ylsup 签名算法 - TODO: 待根据平台文档实现"""
        timestamp = int(time.time())
        app_key = self.supplier.app_key
        app_secret = self.supplier.app_secret
        sign_str = app_key + app_secret + path + str(timestamp)
        app_token = hashlib.sha1(sign_str.encode("utf-8")).hexdigest()
        return app_token, timestamp

    def _build_headers(self, path: str) -> dict[str, str]:
        app_token, timestamp = self._sign(path)
        return {
            "AppId": self.supplier.app_key,
            "AppToken": app_token,
            "AppTimestamp": str(timestamp),
        }

    def _data(self, payload: dict[str, Any]) -> Any:
        """提取上游 data，失败时抛出带上游信息的异常"""
        if payload.get("code") != 0:
            detail = payload.get("message") or payload.get("msg") or "上游接口调用失败"
            raise SupplierClientError(detail)
        data = payload.get("data")
        if data is None:
            detail = payload.get("message") or payload.get("msg") or "上游返回数据缺失 data 字段"
            raise SupplierClientError(detail)
        return data

    def query_balance(self) -> Decimal:
        """查询余额"""
        payload = self.get("/openapi/customer/CustomerAccount/Show").json()
        account = self._data(payload)
        if not isinstance(account, dict) or account.get("balance") is None:
            detail = payload.get("message") or payload.get("msg") or "上游返回数据缺少 balance 字段"
            raise SupplierClientError(detail)

        return Decimal(str(account["balance"]))

    def get_categories(self) -> list[dict[str, Any]]:
        """获取商品分类"""
        payload = self.get("/openapi/customer/Goods/CategoryList").json()
        categories = self._data(payload)
        result: list[dict[str, Any]] = []

        def collect(items: Any, parent_id: str | None = None) -> None:
            if not isinstance(items, list):
                return
            for item in items:
                if not isinstance(item, dict) or "id" not in item or "name" not in item:
                    continue
                result.append(
                    {
                        "id": str(item["id"]),
                        "name": str(item["name"]),
                        "parent_id": str(item.get("parent_id") or parent_id or "0"),
                    }
                )
                collect(item.get("parent_infos"), parent_id=str(item["id"]))

        collect(categories)
        return result

    def query_products_list(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        keyword: str | None = None,
        category_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """查询商品列表"""
        body: dict[str, Any] = {
            "page": page,
            "page_size": page_size,
        }
        # TODO: keyword 对应的上游参数名待确认
        if category_id:
            body["goods_category_id"] = category_id
        payload = self.post("/openapi/customer/Goods/List", json=body).json()
        data = self._data(payload)
        return data if isinstance(data, list) else []

    def query_product_detail(self, product_id: str) -> dict[str, Any]:
        """获取商品详情"""
        params = {"goods_id": product_id}
        payload = self.post("/openapi/customer/Goods/Show", params=params).json()
        data = self._data(payload)
        return data if isinstance(data, dict) else {}

    def create_order(
        self,
        *,
        product_id: str,
        quantity: int,
        customer_order_id: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """向上游下单"""
        body = {
            "goods_id": product_id,
            "buy_number": quantity,
            "buy_params": kwargs,
        }
        if customer_order_id:
            body["customer_order_id"] = customer_order_id
        payload = self.post("/openapi/customer/Goods/Buy", json=body).json()
        data = self._data(payload)
        return data if isinstance(data, dict) else {}

    def query_order(self, order_ids: list[int]) -> dict[str, Any]:
        """查询订单"""
        payload = self.post("/openapi/customer/Order/Show", json={"ids": order_ids}).json()
        data = self._data(payload)
        return data if isinstance(data, dict) else {}

    def cancel_order(self, order_id: str) -> dict[str, Any]:
        """申请退单（status=5 仅申请，不一定退单完成）"""
        body = {
            "id": order_id,
            "status": 5,
        }
        payload = self.post("/openapi/customer/Order/StatusHandle", json=body).json()
        data = self._data(payload)
        return data if isinstance(data, dict) else {}
