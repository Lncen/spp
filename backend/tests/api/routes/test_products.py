"""商品模块：API 与业务测试"""

import uuid
from decimal import Decimal

from fastapi.testclient import TestClient

from app.core.config import settings
from tests.utils.utils import random_lower_string


def create_price_template(
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


def create_category(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    *,
    name: str | None = None,
    parent_id: str | None = None,
    sort: int = 0,
) -> dict:
    data: dict[str, object] = {
        "name": name or random_lower_string(),
        "sort": sort,
        "is_active": True,
    }
    if parent_id is not None:
        data["parent_id"] = parent_id
    response = client.post(
        f"{settings.API_V1_STR}/product-categories/",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    return response.json()


def create_product(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    *,
    price_template_id: str | None = None,
    name: str | None = None,
    category_id: str | None = None,
    status: int = 1,
    source_type: int = 2,
    is_closed: bool = False,
    price_mode: str = "template",
) -> dict:
    if category_id is None:
        category_id = create_category(client, superuser_token_headers)["id"]
    if price_mode == "template":
        pricing = {
            "price_template_id": price_template_id,
            "cost_price": "10.00",
        }
    elif price_mode == "fixed":
        pricing = {
            "cost_price": "10.00",
            "fixed_price": "20.00",
        }
    elif price_mode == "coefficient":
        pricing = {
            "cost_price": "10.00",
            "item_coefficient": "1.50",
        }
    else:
        raise ValueError(f"未知价格模式: {price_mode}")
    data = {
        "name": name or random_lower_string(),
        "category_id": category_id,
        "status": status,
        "source_type": source_type,
        "is_closed": is_closed,
        "pricing": pricing,
        "inventory": {
            "min_quantity": 1,
            "max_quantity": 5,
            "stock": 100,
        },
        "fulfillment": {
            "fulfillment_type": 2,
            "can_refund": True,
            "unit": "件",
        },
        "buy_params": [
            {
                "key": "account",
                "label": "账号",
                "is_required": True,
            }
        ],
    }
    response = client.post(
        f"{settings.API_V1_STR}/products/",
        headers=superuser_token_headers,
        json=data,
    )
    assert response.status_code == 200
    return response.json()


def test_product_routes_require_superuser(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    response = client.get(
        f"{settings.API_V1_STR}/products/",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "权限不足"

    response = client.get(
        f"{settings.API_V1_STR}/product-categories/",
        headers=normal_user_token_headers,
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "权限不足"


def test_create_category_with_child(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    parent = create_category(client, superuser_token_headers)
    child = create_category(
        client,
        superuser_token_headers,
        parent_id=parent["id"],
    )

    assert child["parent_id"] == parent["id"]
    assert child["product_count"] == 0

    response = client.get(
        f"{settings.API_V1_STR}/product-categories/",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    content = response.json()
    category_ids: set[str] = set()

    def collect_category_ids(nodes: list[dict]) -> None:
        for item in nodes:
            category_ids.add(item["id"])
            collect_category_ids(item["children"])

    collect_category_ids(content["data"])
    assert parent["id"] in category_ids
    assert child["id"] in category_ids
    parent_node = next(item for item in content["data"] if item["id"] == parent["id"])
    assert {item["id"] for item in parent_node["children"]} == {child["id"]}

    response = client.get(
        f"{settings.API_V1_STR}/product-categories/{child['id']}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    assert response.json()["parent_id"] == parent["id"]


def test_create_category_rejects_duplicate_name_same_parent(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    name = random_lower_string()
    first = create_category(client, superuser_token_headers, name=name)
    response = client.post(
        f"{settings.API_V1_STR}/product-categories/",
        headers=superuser_token_headers,
        json={"name": name, "parent_id": first["parent_id"]},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "同级分类名称已存在"


def test_update_and_move_category(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    parent_a = create_category(client, superuser_token_headers)
    parent_b = create_category(client, superuser_token_headers)
    child = create_category(
        client,
        superuser_token_headers,
        parent_id=parent_a["id"],
    )

    response = client.put(
        f"{settings.API_V1_STR}/product-categories/{child['id']}",
        headers=superuser_token_headers,
        json={
            "name": "moved",
            "parent_id": parent_b["id"],
            "sort": 5,
        },
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == "moved"
    assert content["parent_id"] == parent_b["id"]
    assert content["sort"] == 5


def test_update_category_rejects_cycle(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    parent = create_category(client, superuser_token_headers)
    child = create_category(
        client,
        superuser_token_headers,
        parent_id=parent["id"],
    )

    response = client.put(
        f"{settings.API_V1_STR}/product-categories/{parent['id']}",
        headers=superuser_token_headers,
        json={"parent_id": child["id"]},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "不能将分类移动到自己的下级分类下"


def test_delete_category_with_children_rejected(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    parent = create_category(client, superuser_token_headers)
    child = create_category(
        client,
        superuser_token_headers,
        parent_id=parent["id"],
    )

    response = client.delete(
        f"{settings.API_V1_STR}/product-categories/{parent['id']}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "请先删除子分类"

    response = client.delete(
        f"{settings.API_V1_STR}/product-categories/{child['id']}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200

    response = client.delete(
        f"{settings.API_V1_STR}/product-categories/{parent['id']}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    assert response.json()["message"] == "商品分类已删除"


def test_delete_category_with_products_rejected(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    template = create_price_template(client, superuser_token_headers)
    category = create_category(client, superuser_token_headers)
    product = create_product(
        client,
        superuser_token_headers,
        price_template_id=template["id"],
        category_id=category["id"],
    )

    response = client.delete(
        f"{settings.API_V1_STR}/product-categories/{category['id']}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "请先删除分类下的商品"

    response = client.delete(
        f"{settings.API_V1_STR}/products/{product['id']}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200

    response = client.delete(
        f"{settings.API_V1_STR}/product-categories/{category['id']}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200


def test_create_product_with_all_configs(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    template = create_price_template(client, superuser_token_headers)
    category = create_category(client, superuser_token_headers)
    product = create_product(
        client,
        superuser_token_headers,
        price_template_id=template["id"],
        category_id=category["id"],
    )

    assert product["category_name"] == category["name"]
    assert product["status"] == 1
    assert product["source_type"] == 2
    assert product["is_closed"] is False
    assert product["pricing"]["price_template_id"] == template["id"]
    assert Decimal(product["pricing"]["cost_price"]) == Decimal("10.00")
    assert product["pricing"]["fixed_price"] is None
    assert product["pricing"]["item_coefficient"] is None
    assert product["pricing"]["rule_type"] == 3
    assert product["pricing"]["config_mode"] == "category"
    assert product["inventory"]["min_quantity"] == 1
    assert product["inventory"]["max_quantity"] == 5
    assert product["inventory"]["stock"] == 100
    assert product["fulfillment"]["fulfillment_type"] == 2
    assert product["fulfillment"]["can_refund"] is True
    assert product["fulfillment"]["unit"] == "件"
    assert product["buy_params"][0]["key"] == "account"
    assert product["buy_params"][0]["label"] == "账号"
    assert product["buy_params"][0]["is_required"] is True


def test_create_product_with_fixed_price(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    product = create_product(
        client,
        superuser_token_headers,
        price_mode="fixed",
    )

    pricing = product["pricing"]
    assert pricing["price_template_id"] is None
    assert Decimal(pricing["fixed_price"]) == Decimal("20.00")
    assert pricing["item_coefficient"] is None
    assert pricing["rule_type"] == 1
    assert pricing["config_mode"] == "fixed_price"


def test_create_product_with_item_coefficient(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    product = create_product(
        client,
        superuser_token_headers,
        price_mode="coefficient",
    )

    pricing = product["pricing"]
    assert pricing["price_template_id"] is None
    assert pricing["fixed_price"] is None
    assert Decimal(pricing["item_coefficient"]) == Decimal("1.50")
    assert pricing["rule_type"] == 2
    assert pricing["config_mode"] == "item_coefficient"


def test_create_product_rejects_multiple_price_rules(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    template = create_price_template(client, superuser_token_headers)
    invalid_pricings = [
        {"price_template_id": template["id"], "fixed_price": "20.00"},
        {"price_template_id": template["id"], "item_coefficient": "1.50"},
        {"fixed_price": "20.00", "item_coefficient": "1.50"},
        {},
    ]
    for pricing in invalid_pricings:
        response = client.post(
            f"{settings.API_V1_STR}/products/",
            headers=superuser_token_headers,
            json={
                "name": random_lower_string(),
                "category_id": create_category(
                    client, superuser_token_headers
                )["id"],
                "pricing": pricing,
            },
        )
        assert response.status_code == 422


def test_list_products_pagination_and_filters(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    template = create_price_template(client, superuser_token_headers)
    category_a = create_category(client, superuser_token_headers)
    category_b = create_category(client, superuser_token_headers)
    prefix = random_lower_string()
    product_a1 = create_product(
        client,
        superuser_token_headers,
        price_template_id=template["id"],
        name=f"{prefix}-a1",
        category_id=category_a["id"],
    )
    product_a2 = create_product(
        client,
        superuser_token_headers,
        price_template_id=template["id"],
        name=f"{prefix}-a2",
        category_id=category_a["id"],
        status=3,
    )
    product_b1 = create_product(
        client,
        superuser_token_headers,
        price_template_id=template["id"],
        name=f"{prefix}-b1",
        category_id=category_b["id"],
        source_type=1,
        is_closed=True,
    )

    response = client.get(
        f"{settings.API_V1_STR}/products/",
        headers=superuser_token_headers,
        params={"name": prefix},
    )
    assert response.status_code == 200
    content = response.json()
    assert content["count"] == 3
    assert {item["name"] for item in content["data"]} == {
        product_a1["name"],
        product_a2["name"],
        product_b1["name"],
    }

    response = client.get(
        f"{settings.API_V1_STR}/products/",
        headers=superuser_token_headers,
        params={"name": prefix, "category_id": category_a["id"]},
    )
    content = response.json()
    assert content["count"] == 2
    assert all(item["category_id"] == category_a["id"] for item in content["data"])

    response = client.get(
        f"{settings.API_V1_STR}/products/",
        headers=superuser_token_headers,
        params={"name": prefix, "status": 3},
    )
    content = response.json()
    assert content["count"] == 1
    assert content["data"][0]["id"] == product_a2["id"]

    response = client.get(
        f"{settings.API_V1_STR}/products/",
        headers=superuser_token_headers,
        params={"name": prefix, "source_type": 1, "is_closed": "true"},
    )
    content = response.json()
    assert content["count"] == 1
    assert content["data"][0]["id"] == product_b1["id"]

    response = client.get(
        f"{settings.API_V1_STR}/products/",
        headers=superuser_token_headers,
        params={"name": prefix, "skip": 1, "limit": 1},
    )
    content = response.json()
    assert content["count"] == 3
    assert len(content["data"]) == 1


def test_update_product(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    template = create_price_template(client, superuser_token_headers)
    category_a = create_category(client, superuser_token_headers)
    category_b = create_category(client, superuser_token_headers)
    product = create_product(
        client,
        superuser_token_headers,
        price_template_id=template["id"],
        category_id=category_a["id"],
    )

    response = client.put(
        f"{settings.API_V1_STR}/products/{product['id']}",
        headers=superuser_token_headers,
        json={
            "name": "updated",
            "category_id": category_b["id"],
            "status": 3,
            "is_closed": True,
            "inventory": {
                "min_quantity": 2,
                "max_quantity": 10,
                "stock": 50,
            },
            "buy_params": [{"key": "qq", "label": "QQ"}],
        },
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == "updated"
    assert content["category_id"] == category_b["id"]
    assert content["category_name"] == category_b["name"]
    assert content["status"] == 3
    assert content["is_closed"] is True
    assert content["inventory"]["min_quantity"] == 2
    assert content["inventory"]["max_quantity"] == 10
    assert content["inventory"]["stock"] == 50
    assert len(content["buy_params"]) == 1
    assert content["buy_params"][0]["key"] == "qq"


def test_update_product_switch_template_to_fixed_price(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    template = create_price_template(client, superuser_token_headers)
    product = create_product(
        client,
        superuser_token_headers,
        price_template_id=template["id"],
    )

    response = client.put(
        f"{settings.API_V1_STR}/products/{product['id']}",
        headers=superuser_token_headers,
        json={
            "pricing": {
                "price_template_id": None,
                "fixed_price": "30.00",
            }
        },
    )
    assert response.status_code == 200
    pricing = response.json()["pricing"]
    assert pricing["price_template_id"] is None
    assert Decimal(pricing["fixed_price"]) == Decimal("30.00")
    assert pricing["item_coefficient"] is None
    assert pricing["rule_type"] == 1
    assert pricing["config_mode"] == "fixed_price"


def test_update_product_rejects_multiple_price_rules(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    template = create_price_template(client, superuser_token_headers)
    product = create_product(
        client,
        superuser_token_headers,
        price_template_id=template["id"],
    )

    response = client.put(
        f"{settings.API_V1_STR}/products/{product['id']}",
        headers=superuser_token_headers,
        json={
            "pricing": {
                "price_template_id": template["id"],
                "fixed_price": "30.00",
            }
        },
    )
    assert response.status_code == 400
    assert (
        response.json()["detail"]
        == "固定价格、商品系数、价格模板三者必须且只能设置一个"
    )


def test_update_product_supplier_clear(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    template = create_price_template(client, superuser_token_headers)
    category = create_category(client, superuser_token_headers)
    response = client.post(
        f"{settings.API_V1_STR}/products/",
        headers=superuser_token_headers,
        json={
            "name": random_lower_string(),
            "category_id": category["id"],
            "pricing": {"price_template_id": template["id"]},
            "supplier": {"supplier_id": None, "sku_id": "SKU-001"},
        },
    )
    assert response.status_code == 200
    product = response.json()
    assert product["supplier"]["sku_id"] == "SKU-001"

    response = client.put(
        f"{settings.API_V1_STR}/products/{product['id']}",
        headers=superuser_token_headers,
        json={"supplier": None},
    )
    assert response.status_code == 200
    assert response.json()["supplier"] is None


def test_update_product_clears_buy_params_with_null(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    template = create_price_template(client, superuser_token_headers)
    product = create_product(
        client,
        superuser_token_headers,
        price_template_id=template["id"],
    )

    response = client.put(
        f"{settings.API_V1_STR}/products/{product['id']}",
        headers=superuser_token_headers,
        json={"buy_params": None},
    )
    assert response.status_code == 200
    assert response.json()["buy_params"] == []


def test_delete_product(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    template = create_price_template(client, superuser_token_headers)
    product = create_product(
        client,
        superuser_token_headers,
        price_template_id=template["id"],
    )

    response = client.delete(
        f"{settings.API_V1_STR}/products/{product['id']}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 200
    assert response.json()["message"] == "商品已删除"

    response = client.get(
        f"{settings.API_V1_STR}/products/{product['id']}",
        headers=superuser_token_headers,
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "商品不存在"


def test_create_product_rejects_price_rule_conflict(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    template = create_price_template(client, superuser_token_headers)
    response = client.post(
        f"{settings.API_V1_STR}/products/",
        headers=superuser_token_headers,
        json={
            "name": random_lower_string(),
            "pricing": {
                "price_template_id": template["id"],
                "fixed_price": "20.00",
                "item_coefficient": "1.50",
            },
        },
    )
    assert response.status_code == 422


def test_create_product_rejects_invalid_inventory_bounds(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    template = create_price_template(client, superuser_token_headers)
    category = create_category(client, superuser_token_headers)
    response = client.post(
        f"{settings.API_V1_STR}/products/",
        headers=superuser_token_headers,
        json={
            "name": random_lower_string(),
            "category_id": category["id"],
            "pricing": {"price_template_id": template["id"]},
            "inventory": {"min_quantity": 5, "max_quantity": 1},
        },
    )
    assert response.status_code == 422


def test_create_product_requires_category(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    template = create_price_template(client, superuser_token_headers)
    response = client.post(
        f"{settings.API_V1_STR}/products/",
        headers=superuser_token_headers,
        json={
            "name": random_lower_string(),
            "pricing": {"price_template_id": template["id"]},
        },
    )
    assert response.status_code == 422
    assert "category_id" in response.json()["detail"][0]["loc"]


def test_create_product_rejects_decimal_purchase_step(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    template = create_price_template(client, superuser_token_headers)
    category = create_category(client, superuser_token_headers)
    response = client.post(
        f"{settings.API_V1_STR}/products/",
        headers=superuser_token_headers,
        json={
            "name": random_lower_string(),
            "category_id": category["id"],
            "pricing": {"price_template_id": template["id"]},
            "inventory": {"purchase_step": 1.5},
        },
    )
    assert response.status_code == 422
    assert "purchase_step" in response.json()["detail"][0]["loc"]


def test_create_product_rejects_missing_price_template(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    category = create_category(client, superuser_token_headers)
    response = client.post(
        f"{settings.API_V1_STR}/products/",
        headers=superuser_token_headers,
        json={
            "name": random_lower_string(),
            "category_id": category["id"],
            "pricing": {"price_template_id": str(uuid.uuid4())},
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "价格模板不存在"


def test_create_product_rejects_missing_category(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    template = create_price_template(client, superuser_token_headers)
    response = client.post(
        f"{settings.API_V1_STR}/products/",
        headers=superuser_token_headers,
        json={
            "name": random_lower_string(),
            "category_id": str(uuid.uuid4()),
            "pricing": {"price_template_id": template["id"]},
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "商品分类不存在"


def test_create_product_rejects_duplicate_buy_param_keys(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    template = create_price_template(client, superuser_token_headers)
    category = create_category(client, superuser_token_headers)
    response = client.post(
        f"{settings.API_V1_STR}/products/",
        headers=superuser_token_headers,
        json={
            "name": random_lower_string(),
            "category_id": category["id"],
            "pricing": {"price_template_id": template["id"]},
            "buy_params": [
                {"key": "account", "label": "账号"},
                {"key": "account", "label": "另一个账号"},
            ],
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "购买参数 key 不能重复"


def test_update_product_rejects_null_required_configs(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    template = create_price_template(client, superuser_token_headers)
    product = create_product(
        client,
        superuser_token_headers,
        price_template_id=template["id"],
    )
    base_url = f"{settings.API_V1_STR}/products/{product['id']}"

    response = client.put(
        base_url,
        headers=superuser_token_headers,
        json={"pricing": None},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "商品必须保留定价配置"

    response = client.put(
        base_url,
        headers=superuser_token_headers,
        json={"inventory": None},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "商品必须保留库存配置"

    response = client.put(
        base_url,
        headers=superuser_token_headers,
        json={"fulfillment": None},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "商品必须保留履约配置"
