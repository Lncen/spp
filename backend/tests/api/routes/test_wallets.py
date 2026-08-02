import uuid
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.modules.user.models import User
from tests.utils.user import authentication_token_from_email, create_random_user


def _create_wallet_user(client: TestClient, db: Session) -> tuple[dict[str, str], User]:
    """创建随机用户并返回其认证头和用户对象"""
    user = create_random_user(db)
    headers = authentication_token_from_email(client=client, email=user.email, db=db)
    return headers, user


def _read_wallet_id(client: TestClient, headers: dict[str, str]) -> str:
    response = client.get(f"{settings.API_V1_STR}/wallets/me", headers=headers)
    assert response.status_code == 200
    return response.json()["id"]


def test_read_wallet_me_creates_wallet(client: TestClient, db: Session) -> None:
    headers, user = _create_wallet_user(client, db)
    response = client.get(f"{settings.API_V1_STR}/wallets/me", headers=headers)
    assert response.status_code == 200
    content = response.json()
    assert content["user_id"] == str(user.id)
    assert Decimal(content["balance"]) == Decimal("0.00")
    assert content["currency"] == "CNY"


def test_read_wallet_transactions_empty(client: TestClient, db: Session) -> None:
    headers, _ = _create_wallet_user(client, db)
    response = client.get(
        f"{settings.API_V1_STR}/wallets/me/transactions", headers=headers
    )
    assert response.status_code == 200
    content = response.json()
    assert content["count"] == 0
    assert content["data"] == []


def test_adjust_wallet_balance_add(
    client: TestClient, db: Session, superuser_token_headers: dict[str, str]
) -> None:
    headers, _ = _create_wallet_user(client, db)
    wallet_id = _read_wallet_id(client, headers)
    response = client.post(
        f"{settings.API_V1_STR}/wallets/{wallet_id}/adjust",
        headers=superuser_token_headers,
        json={"amount": "100.50", "remark": "测试入账"},
    )
    assert response.status_code == 200
    content = response.json()
    assert Decimal(content["amount"]) == Decimal("100.50")
    assert Decimal(content["balance_after"]) == Decimal("100.50")
    assert content["tx_type"] == "adjust"

    wallet_response = client.get(f"{settings.API_V1_STR}/wallets/me", headers=headers)
    assert Decimal(wallet_response.json()["balance"]) == Decimal("100.50")

    transactions_response = client.get(
        f"{settings.API_V1_STR}/wallets/me/transactions", headers=headers
    )
    transactions = transactions_response.json()
    assert transactions["count"] == 1
    assert Decimal(transactions["data"][0]["amount"]) == Decimal("100.50")


def test_adjust_wallet_balance_deduct(
    client: TestClient, db: Session, superuser_token_headers: dict[str, str]
) -> None:
    headers, _ = _create_wallet_user(client, db)
    wallet_id = _read_wallet_id(client, headers)
    client.post(
        f"{settings.API_V1_STR}/wallets/{wallet_id}/adjust",
        headers=superuser_token_headers,
        json={"amount": "100.00", "remark": "测试入账"},
    )
    response = client.post(
        f"{settings.API_V1_STR}/wallets/{wallet_id}/adjust",
        headers=superuser_token_headers,
        json={"amount": "-40.00", "remark": "测试扣款"},
    )
    assert response.status_code == 200
    content = response.json()
    assert Decimal(content["amount"]) == Decimal("-40.00")
    assert Decimal(content["balance_after"]) == Decimal("60.00")


def test_adjust_wallet_balance_insufficient(
    client: TestClient, db: Session, superuser_token_headers: dict[str, str]
) -> None:
    headers, _ = _create_wallet_user(client, db)
    wallet_id = _read_wallet_id(client, headers)
    response = client.post(
        f"{settings.API_V1_STR}/wallets/{wallet_id}/adjust",
        headers=superuser_token_headers,
        json={"amount": "-1.00", "remark": "测试余额不足"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "余额不足，无法扣减"

    wallet_response = client.get(f"{settings.API_V1_STR}/wallets/me", headers=headers)
    assert Decimal(wallet_response.json()["balance"]) == Decimal("0.00")


def test_adjust_wallet_balance_zero_amount(
    client: TestClient, db: Session, superuser_token_headers: dict[str, str]
) -> None:
    headers, _ = _create_wallet_user(client, db)
    wallet_id = _read_wallet_id(client, headers)
    response = client.post(
        f"{settings.API_V1_STR}/wallets/{wallet_id}/adjust",
        headers=superuser_token_headers,
        json={"amount": "0.00", "remark": "零金额"},
    )
    assert response.status_code == 422
    assert response.json()["detail"] == "调账金额不能为 0"


def test_adjust_wallet_not_found(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/wallets/{uuid.uuid4()}/adjust",
        headers=superuser_token_headers,
        json={"amount": "10.00", "remark": "钱包不存在"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "钱包不存在"


def test_adjust_wallet_requires_superuser(
    client: TestClient, db: Session, normal_user_token_headers: dict[str, str]
) -> None:
    headers, _ = _create_wallet_user(client, db)
    wallet_id = _read_wallet_id(client, headers)
    response = client.post(
        f"{settings.API_V1_STR}/wallets/{wallet_id}/adjust",
        headers=normal_user_token_headers,
        json={"amount": "10.00", "remark": "无权限"},
    )
    assert response.status_code == 403


def test_read_wallets_superuser(
    client: TestClient, db: Session, superuser_token_headers: dict[str, str]
) -> None:
    headers, _ = _create_wallet_user(client, db)
    wallet_id = _read_wallet_id(client, headers)
    response = client.get(
        f"{settings.API_V1_STR}/wallets/", headers=superuser_token_headers
    )
    assert response.status_code == 200
    content = response.json()
    assert content["count"] >= 1
    assert any(wallet["id"] == wallet_id for wallet in content["data"])
