"""ylsup 平台 API client"""
import time
from decimal import Decimal
from typing import Any
import hashlib
from app.modules.supplier.service.clients.base import (
    SupplierClientBase,
    SupplierClientError,
)


class YlsupClient(SupplierClientBase):
    """ylsup 平台 API 客户端"""

    def _sign_request(self, url: str ) -> tuple[str, int]:
        """ylsup 签名算法 - TODO: 待根据平台文档实现"""
        timestamp = int(time.time())
        app_key = self.supplier.app_key
        app_secret = self.supplier.app_secret
        sign_str = app_key + app_secret + url + str(timestamp)
        app_token = hashlib.sha1(sign_str.encode("utf-8")).hexdigest()
        return app_token, timestamp

    def _build_headers(self, url: str) -> dict[str, str]:
        app_token, timestamp = self._sign_request(url)
        return {
            "AppId": self.supplier.app_key,
            "AppToken": app_token,
            "AppTimestamp": str(timestamp),
            "Content-Type": "application/json",
        }

    def query_balance(self) -> Decimal:
        """查询余额"""
        data = self._request("GET", "/api/balance").json()
        # TODO: 根据实际响应格式解析
        return Decimal(str(data.get("balance", 0)))

    def probe(self) -> bool:
        """探测上游 API 是否可达"""
        try:
            self._request("GET", "/api/ping")
            return True
        except SupplierClientError:
            return False

    def query_products(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        keyword: str | None = None,
        category_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """查询商品列表"""
        params: dict[str, Any] = {
            "page": page,
            "page_size": page_size,
        }
        if keyword:
            params["keyword"] = keyword
        if category_id:
            params["category_id"] = category_id
        data = self._request("GET", "/api/products", params=params).json()
        # TODO: 根据实际响应格式解析
        return data.get("list", [])

    def get_product_detail(self, product_id: str) -> dict[str, Any]:
        """获取商品详情"""
        data = self._request("GET", f"/api/products/{product_id}").json()
        # TODO: 根据实际响应格式解析
        return data

    def get_categories(self) -> list[dict[str, Any]]:
        """获取商品分类"""
        data = self._request("GET", "/api/categories").json()
        # TODO: 根据实际响应格式解析
        return data.get("list", [])

    def create_order(
        self,
        *,
        product_id: str,
        quantity: int,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """向上游下单"""
        body = {
            "product_id": product_id,
            "quantity": quantity,
            **kwargs,
        }
        data = self._request("POST", "/api/orders", json=body).json()
        # TODO: 根据实际响应格式解析
        return data

    def query_order(self, order_id: str) -> dict[str, Any]:
        """查询订单"""
        data = self._request("GET", f"/api/orders/{order_id}").json()
        # TODO: 根据实际响应格式解析
        return data

    def cancel_order(self, order_id: str) -> dict[str, Any]:
        """取消订单"""
        data = self._request("POST", f"/api/orders/{order_id}/cancel").json()
        # TODO: 根据实际响应格式解析
        return data
