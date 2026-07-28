"""供应商 API client 抽象基类"""


from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any, Self

import httpx

from app.modules.supplier.models import Supplier


class SupplierClientError(Exception):
    """供应商 API 调用异常"""


class SupplierClientBase(ABC):
    """供应商 API client 抽象基类

    封装 HTTP 请求、重试与错误处理。
    子类必须实现所有抽象方法。
    """

    def __init__(self, supplier: Supplier) -> None:
        self.supplier = supplier
        self._client = httpx.Client(
            base_url=supplier.base_url,
            timeout=supplier.timeout_seconds,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )

    @abstractmethod
    def _sign_request(self, params: dict[str, Any]) -> dict[str, Any]:
        """生成带签名的请求参数

        每个平台的签名算法不同，子类必须重写。
        接收原始参数字典，返回添加了签名参数的副本。
        """
        ...

    @abstractmethod
    def query_balance(self) -> Decimal:
       """查询供应商余额"""
       ...

    @abstractmethod
    def probe(self) -> bool:
        """探测上游 API 是否可达

        发送轻量请求验证连通性，返回 True 表示可达。
        """
        ...

    @abstractmethod
    def query_products(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        keyword: str | None = None,
        category_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """查询商品列表"""
        ...

    @abstractmethod
    def get_product_detail(self, product_id: str) -> dict[str, Any]:
        """获取商品详情"""
        ...

    @abstractmethod
    def get_categories(self) -> list[dict[str, Any]]:
        """获取商品分类"""
        ...

    @abstractmethod
    def create_order(
        self,
        *,
        product_id: str,
        quantity: int,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """向上游下单"""
        ...

    @abstractmethod
    def query_order(self, order_id: str) -> dict[str, Any]:
        """查询订单"""
        ...

    @abstractmethod
    def cancel_order(self, order_id: str) -> dict[str, Any]:
        """取消订单"""
        ...

    def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """通用请求方法，含重试与异常包装

        - 4xx 客户端错误：不重试，直接抛出 SupplierClientError
        - 5xx 服务端错误：按 supplier.retry_times 重试，指数退避
        - 网络/超时错误：按 supplier.retry_times 重试
        - 其他请求错误：直接抛出 SupplierClientError
        """
        if "params" in kwargs:
            kwargs["params"] = self._sign_request(kwargs["params"])

        last_error: Exception | None = None
        max_retries = self.supplier.retry_times

        for attempt in range(max_retries):
            try:
                response = self._client.request(method, path, **kwargs)

                if response.is_success:
                    return response

                # 4xx：客户端错误，不重试
                if 400 <= response.status_code < 500:
                    raise SupplierClientError(
                        f"供应商 API 返回 {response.status_code}: {response.text[:500]}"
                    )

                # 5xx：服务端错误，重试
                last_error = SupplierClientError(
                    f"供应商 API 返回 {response.status_code}: {response.text[:500]}"
                )

            except httpx.TimeoutException as e:
                last_error = SupplierClientError(f"供应商 API 超时: {e}")
            except httpx.NetworkError as e:
                last_error = SupplierClientError(f"供应商 API 网络错误: {e}")
            except httpx.RequestError as e:
                # 非超时/网络的请求错误（如 DNS 解析），直接抛出
                raise SupplierClientError(f"供应商 API 请求失败: {e}") from e

            if attempt < max_retries - 1:
                import time

                time.sleep(min(2**attempt, 10))

        raise last_error  # type: ignore[misc]

    def close(self) -> None:
        """释放 HTTP 连接"""
        self._client.close()
 
    def __enter__(self) -> Self:
        return self
 
    def __exit__(self, *args: object) -> None:
        self.close()
