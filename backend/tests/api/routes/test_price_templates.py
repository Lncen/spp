"""价格模板模块：API 与价格计算测试"""

import uuid
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.modules.level.models import UserLevel
from app.modules.price_template.models import PriceTemplate
from app.modules.price_template.service import get_user_price
from tests.utils.utils import random_lower_string


def create_random_price_template(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> dict:
    data = {
        "name": random_lower_string(),
        "description": "test template",
        "rules": [{"level": 1, "discount_rate": 0.9}],
    }
    response = client.post(
        f"{settings.API_V1_STR}/price-templates/",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    return response.json()


def test_create_price_template_fills_default_rules(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    data = {
        "name": random_lower_string(),
        "rules": [
            {"level": 1, "discount_rate": 0.9},
            {"level": 5, "discount_rate": 1.2},
        ],
    }
    response = client.post(
        f"{settings.API_V1_STR}/price-templates/",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == data["name"]
    assert len(content["rules"]) == 10
    rules_by_level = {
        rule["level"]: rule["discount_rate"] for rule in content["rules"]
    }
    assert Decimal(rules_by_level[1]) == Decimal("0.9")
    assert Decimal(rules_by_level[5]) == Decimal("1.2")
    assert Decimal(rules_by_level[2]) == Decimal("1.5")
    assert Decimal(rules_by_level[10]) == Decimal("1.5")


def test_create_price_template_requires_superuser(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    data = {"name": random_lower_string()}
    response = client.post(
        f"{settings.API_V1_STR}/price-templates/",
        headers=normal_user_token_headers,
        json=data,
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "权限不足"


def test_read_price_templates_requires_superuser(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/price-templates/",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "权限不足"


def test_create_price_template_rejects_duplicate_level(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    data = {
        "name": random_lower_string(),
        "rules": [
            {"level": 1, "discount_rate": 0.9},
            {"level": 1, "discount_rate": 1.1},
        ],
    }
    response = client.post(
        f"{settings.API_V1_STR}/price-templates/",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 422


def test_update_price_template_only_overrides_sent_levels(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    template = create_random_price_template(client, superuser_token_headers)
    data = {"rules": [{"level": 2, "discount_rate": 0.8}]}
    response = client.put(
        f"{settings.API_V1_STR}/price-templates/{template['id']}",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    rules_by_level = {
        rule["level"]: rule["discount_rate"] for rule in content["rules"]
    }
    assert len(content["rules"]) == 10
    assert Decimal(rules_by_level[1]) == Decimal("0.9")
    assert Decimal(rules_by_level[2]) == Decimal("0.8")


def test_delete_price_template(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    template = create_random_price_template(client, superuser_token_headers)
    response = client.delete(
        f"{settings.API_V1_STR}/price-templates/{template['id']}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    assert response.json()["message"] == "价格模板已删除"

    response = client.get(
        f"{settings.API_V1_STR}/price-templates/{template['id']}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "价格模板不存在"


def test_get_user_price_by_level(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    template = create_random_price_template(client, superuser_token_headers)
    level = db.exec(select(UserLevel).where(UserLevel.level == 1)).one()
    assert get_user_price(
        session=db,
        base_price=Decimal("100.00"),
        price_template_id=uuid.UUID(template["id"]),
        user_level_id=level.id,
    ) == Decimal("90.00")


def test_get_user_price_defaults_to_15_discount_when_rule_missing(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    template = create_random_price_template(client, superuser_token_headers)
    assert get_user_price(
        session=db,
        base_price=Decimal("100.00"),
        price_template_id=uuid.UUID(template["id"]),
        user_level_id=uuid.uuid4(),
    ) == Decimal("150.00")


def test_get_user_price_falls_back_to_base_price_when_template_disabled(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    template = create_random_price_template(client, superuser_token_headers)
    db_template = db.get(PriceTemplate, uuid.UUID(template["id"]))
    assert db_template is not None
    db_template.is_active = False
    db.add(db_template)
    db.commit()

    assert get_user_price(
        session=db,
        base_price=Decimal("100.00"),
        price_template_id=uuid.UUID(template["id"]),
        user_level_id=uuid.uuid4(),
    ) == Decimal("100.00")


def test_get_user_price_falls_back_to_base_price_without_template(
    db: Session,
) -> None:
    assert get_user_price(
        session=db,
        base_price=Decimal("100.00"),
        price_template_id=None,
        user_level_id=None,
    ) == Decimal("100.00")
