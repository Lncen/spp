import time
from abc import ABC, ABCMeta, abstractmethod
from decimal import Decimal
from typing import Any, Self

import httpx
from sqlmodel import Session

from app.modules.supplier.models import Supplier
from app.modules.supplier.service.dto import (
    UpstreamCategory,
    UpstreamProductDetail,
    UpstreamProductSummary,
)


class SupplierClientError(Exception):
    """供应商 API 调用异常"""


# ================= 1. 元类：仅负责自动注册 =================
class ClientMeta(ABCMeta):
    _registry: dict[str, type[SupplierClientBase]] = {}

    def __new__(
        cls,
        name: str,
        bases: tuple[type[Any], ...],
        attrs: dict[str, Any],
    ) -> type[Any]:
        new_cls = super().__new__(cls, name, bases, attrs)

        if name != "SupplierClientBase" and issubclass(new_cls, SupplierClientBase):
            registry_key = getattr(new_cls, "code", None)
            if not registry_key:
                raise TypeError(f"供应商客户端 {name} 缺少必需的类属性 'code'")

            cls._registry[registry_key] = new_cls
        return new_cls

    @classmethod
    def get_client(
        cls,
        supplier: Supplier,
        session: Session | None = None,
    ) -> SupplierClientBase:
        """工厂方法：传入 supplier，自动路由并返回实例"""
        client_cls = cls._registry.get(supplier.platform)
        if not client_cls:
            raise SupplierClientError(
                f"未找到 platform='{supplier.platform}' 的供应商客户端。"
                f"已注册: {list(cls._registry.keys())}"
            )
        return client_cls(supplier, session=session)


# ================= 2. HTTP 传输层基类 =================
class BaseHttpClient(ABC):
    code: str  # 仅作为注册键，不参与 HTTP 配置

    def __init__(self, supplier: Supplier, session: Session | None = None) -> None:
        self.supplier = supplier
        self._session = session

        self._client = httpx.Client(
            base_url=supplier.base_url,
            timeout=supplier.timeout_seconds,
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )

    @abstractmethod
    def _build_headers(self, path: str) -> dict[str, str]: ...

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        custom_headers = self._build_headers(path)
        if "headers" in kwargs:
            kwargs["headers"] = {**kwargs["headers"], **custom_headers}
        else:
            kwargs["headers"] = custom_headers

        last_error: Exception | None = None
        # 非幂等请求不自动重试，避免超时后重复下单等副作用
        idempotent = method.upper() in {"GET", "HEAD", "OPTIONS"}
        max_retries = self.supplier.retry_times + 1 if idempotent else 1

        for attempt in range(max_retries):
            try:
                response = self._client.request(method, path, **kwargs)

                if response.is_success:
                    # 成功：更新为 online（限流）
                    self._update_supplier_status("online")
                    return response

                if 400 <= response.status_code < 500 and response.status_code != 429:
                    raise SupplierClientError(
                        f"供应商 API 返回 {response.status_code}: {response.text[:500]}"
                    )

                last_error = SupplierClientError(
                    f"供应商 API 返回 {response.status_code}: {response.text[:500]}"
                )

            except httpx.TimeoutException as e:
                last_error = SupplierClientError(f"供应商 API 超时: {e}")
            except httpx.NetworkError as e:
                last_error = SupplierClientError(f"供应商 API 网络错误: {e}")
                # 网络错误时立即标记为 offline（在最后一次重试后）
            except httpx.RequestError as e:
                raise SupplierClientError(f"供应商 API 请求失败: {e}") from e

            if attempt < max_retries - 1:
                wait_time = min(2 ** attempt, 10)
                time.sleep(wait_time)

        # 所有重试都失败了，更新为 offline
        if last_error:
            self._update_supplier_status("offline", str(last_error)[:200])

        raise last_error  # type: ignore[misc]

    def _update_supplier_status(self, status: str, reason: str = ""):
        """
        更新供应商状态（带限流）

        Args:
            status: "online" 或 "offline"
            reason: 离线原因（仅当 status="offline" 时有效）
        """
        if self._session is None:
            return

        # 状态没变化就不更新
        if self.supplier.connection_status == status:
            return

        current_time = time.time()
        last_update = getattr(self.supplier, '_last_status_update', 0)

        # online 限流：60秒内不重复更新
        if status == "online" and current_time - last_update < 60:
            return

        # offline 不限流，但也可以设置更短的间隔（可选）
        # if status == "offline" and current_time - last_update < 5:
        #     return

        # 更新状态
        self.supplier.connection_status = status
        self.supplier._last_status_update = current_time

        if status == "offline" and reason:
            # 如果有 offline_reason 字段就记录
            if hasattr(self.supplier, 'offline_reason'):
                self.supplier.offline_reason = reason

        try:
            self._session.add(self.supplier)
            self._session.commit()
        except Exception as e:
            # 状态更新失败不影响主流程
            self._session.rollback()

    def get(self, path: str, **kwargs: Any) -> httpx.Response:
        return self._request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> httpx.Response:
        return self._request("POST", path, **kwargs)

    def close(self) -> None:
        """关闭 HTTP client 及其连接池"""
        self._client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


# ================= 3. 供应商业务抽象基类 =================
class SupplierClientBase(BaseHttpClient, metaclass=ClientMeta):
    @abstractmethod
    def query_balance(self) -> Decimal: ...

    @abstractmethod
    def query_products_list(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        keyword: str | None = None,
        category_id: str | None = None,
    ) -> list[UpstreamProductSummary]: ...

    @abstractmethod
    def query_product_detail(self, product_id: str) -> UpstreamProductDetail: ...

    @abstractmethod
    def get_categories(self) -> list[UpstreamCategory]: ...

    @abstractmethod
    def create_order(
        self, *, product_id: str, quantity: int, **kwargs: Any
    ) -> dict[str, Any]: ...

    @abstractmethod
    def query_order(self, order_ids: list[int]) -> dict[str, Any]: ...

    @abstractmethod
    def cancel_order(self, order_id: str) -> dict[str, Any]: ...
