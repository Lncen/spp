from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, delete

from app.core.config import settings
from app.core.db import engine, init_db
from app.main import app
from app.modules.image.models import Image, ImageCategory
from app.modules.item.models import Item
from app.modules.price_template.models import PriceTemplate, PriceTemplateRule
from app.modules.product.category.models import ProductCategory
from app.modules.product.product.models import (
    Product,
    ProductBuyParam,
    ProductFulfillment,
    ProductInventory,
    ProductPricing,
    ProductSupplier,
)
from app.modules.supplier.models import Supplier
from app.modules.user.models import User
from tests.utils.user import authentication_token_from_email
from tests.utils.utils import get_superuser_token_headers


@pytest.fixture(scope="session", autouse=True)
def db() -> Generator[Session]:
    with Session(engine) as session:
        init_db(session)
        # 新模块表尚未生成迁移，测试环境单独建表；产品库由 Alembic 迁移建表
        SQLModel.metadata.create_all(
            engine,
            tables=[
                PriceTemplate.__table__,
                PriceTemplateRule.__table__,
                ProductCategory.__table__,
                Product.__table__,
                ProductSupplier.__table__,
                ProductPricing.__table__,
                ProductInventory.__table__,
                ProductFulfillment.__table__,
                ProductBuyParam.__table__,
            ],
        )
        yield session
        statement = delete(ProductBuyParam)
        session.execute(statement)
        statement = delete(ProductInventory)
        session.execute(statement)
        statement = delete(ProductFulfillment)
        session.execute(statement)
        statement = delete(ProductPricing)
        session.execute(statement)
        statement = delete(ProductSupplier)
        session.execute(statement)
        statement = delete(Product)
        session.execute(statement)
        statement = delete(ProductCategory)
        session.execute(statement)
        statement = delete(Item)
        session.execute(statement)
        statement = delete(Image)
        session.execute(statement)
        statement = delete(ImageCategory)
        session.execute(statement)
        statement = delete(PriceTemplateRule)
        session.execute(statement)
        statement = delete(PriceTemplate)
        session.execute(statement)
        statement = delete(Supplier)
        session.execute(statement)
        statement = delete(User)
        session.execute(statement)
        session.commit()


@pytest.fixture(scope="module")
def client() -> Generator[TestClient]:
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def superuser_token_headers(client: TestClient) -> dict[str, str]:
    return get_superuser_token_headers(client)


@pytest.fixture(scope="module")
def normal_user_token_headers(client: TestClient, db: Session) -> dict[str, str]:
    return authentication_token_from_email(
        client=client, email=settings.EMAIL_TEST_USER, db=db
    )
