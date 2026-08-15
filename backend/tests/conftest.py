from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlmodel import Session, SQLModel, delete

from app.core.config import settings
from app.core.db import engine, init_db
from app.main import app
from app.modules.auth.models import RefreshToken
from app.modules.automation.models import (
    AutomationEvent,
    AutomationRule,
    AutomationTask,
    AutomationTaskArchive,
)
from app.modules.customer_service.models import (
    Conversation,
    ConversationMessage,
)
from app.modules.image.models import Image, ImageCategory
from app.modules.item.models import Item
from app.modules.order.models import Order, OrderParam
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
from app.modules.wallet.models import Wallet, WalletTransaction
from tests.utils.user import authentication_token_from_email
from tests.utils.utils import get_superuser_token_headers


@pytest.fixture(scope="session", autouse=True)
def db() -> Generator[Session]:
    with Session(engine) as session:
        # 迁移文件由用户按项目规范自行生成，测试库先幂等补齐新增用户字段
        with engine.begin() as conn:
            conn.execute(
                text(
                    'ALTER TABLE "user" '
                    "ADD COLUMN IF NOT EXISTS can_order "
                    "BOOLEAN NOT NULL DEFAULT TRUE"
                )
            )
            conn.execute(
                text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS avatar_id UUID')
            )
            conn.execute(
                text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS remark VARCHAR(255)')
            )
            conn.execute(
                text('ALTER TABLE "user" ADD COLUMN IF NOT EXISTS bio VARCHAR(1000)')
            )
            conn.execute(
                text(
                    'CREATE INDEX IF NOT EXISTS ix_user_can_order ON "user" (can_order)'
                )
            )
            conn.execute(
                text(
                    "ALTER TABLE price_template "
                    "ADD COLUMN IF NOT EXISTS is_default "
                    "BOOLEAN NOT NULL DEFAULT FALSE"
                )
            )
            for column_sql in (
                "ALTER TABLE orders ADD COLUMN IF NOT EXISTS product_id UUID",
                "ALTER TABLE product ADD COLUMN IF NOT EXISTS sync_status INTEGER",
                (
                    "ALTER TABLE product ADD COLUMN IF NOT EXISTS synced_at "
                    "TIMESTAMP WITH TIME ZONE"
                ),
                (
                    "ALTER TABLE product_supplier ADD COLUMN IF NOT EXISTS "
                    "upstream_name VARCHAR(255)"
                ),
                (
                    "ALTER TABLE orders ADD COLUMN IF NOT EXISTS product_name "
                    "VARCHAR(255) NOT NULL DEFAULT ''"
                ),
                (
                    "ALTER TABLE orders ADD COLUMN IF NOT EXISTS quantity "
                    "INTEGER NOT NULL DEFAULT 1"
                ),
                (
                    "ALTER TABLE orders ADD COLUMN IF NOT EXISTS start_quantity "
                    "INTEGER NOT NULL DEFAULT 0"
                ),
                (
                    "ALTER TABLE orders ADD COLUMN IF NOT EXISTS current_quantity "
                    "INTEGER NOT NULL DEFAULT 0"
                ),
                (
                    "ALTER TABLE orders ADD COLUMN IF NOT EXISTS unit_price "
                    "NUMERIC(18,2) NOT NULL DEFAULT 0"
                ),
                (
                    "ALTER TABLE orders ADD COLUMN IF NOT EXISTS subtotal "
                    "NUMERIC(18,2) NOT NULL DEFAULT 0"
                ),
                (
                    "ALTER TABLE orders ADD COLUMN IF NOT EXISTS base_price "
                    "NUMERIC(18,8) NOT NULL DEFAULT 0"
                ),
                (
                    "ALTER TABLE orders ADD COLUMN IF NOT EXISTS cost_price "
                    "NUMERIC(18,8) NOT NULL DEFAULT 0"
                ),
                (
                    "ALTER TABLE orders ADD COLUMN IF NOT EXISTS loss_price "
                    "NUMERIC(18,8) NOT NULL DEFAULT 0"
                ),
                (
                    "ALTER TABLE orders ADD COLUMN IF NOT EXISTS params "
                    "JSON NOT NULL DEFAULT '{}'::json"
                ),
                (
                    "ALTER TABLE orders ADD COLUMN IF NOT EXISTS fulfillment_type "
                    "INTEGER NOT NULL DEFAULT 1"
                ),
                (
                    "ALTER TABLE orders ADD COLUMN IF NOT EXISTS supplier_order_id "
                    "VARCHAR(255)"
                ),
                ("ALTER TABLE orders ADD COLUMN IF NOT EXISTS supplier_id UUID"),
                ("ALTER TABLE orders ADD COLUMN IF NOT EXISTS sku_id VARCHAR(255)"),
                (
                    "ALTER TABLE orders ADD COLUMN IF NOT EXISTS can_refund "
                    "BOOLEAN NOT NULL DEFAULT FALSE"
                ),
            ):
                conn.execute(text(column_sql))
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_orders_product_id ON orders (product_id)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_orders_supplier_order_id "
                    "ON orders (supplier_order_id)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_orders_supplier_id "
                    "ON orders (supplier_id)"
                )
            )
            conn.execute(
                text("CREATE INDEX IF NOT EXISTS ix_orders_sku_id ON orders (sku_id)")
            )
        init_db(session)
        # 新模块表尚未生成迁移，测试环境单独建表；产品库由 Alembic 迁移建表
        SQLModel.metadata.create_all(
            engine,
            tables=[
                RefreshToken.__table__,
                Conversation.__table__,
                ConversationMessage.__table__,
                AutomationTask.__table__,
                AutomationTaskArchive.__table__,
                AutomationEvent.__table__,
                AutomationRule.__table__,
                PriceTemplate.__table__,
                PriceTemplateRule.__table__,
                ProductCategory.__table__,
                Product.__table__,
                ProductSupplier.__table__,
                ProductPricing.__table__,
                ProductInventory.__table__,
                ProductFulfillment.__table__,
                ProductBuyParam.__table__,
                Order.__table__,
                OrderParam.__table__,
                Wallet.__table__,
                WalletTransaction.__table__,
            ],
        )
        yield session
        statement = delete(OrderParam)
        session.execute(statement)
        statement = delete(Order)
        session.execute(statement)
        statement = delete(ConversationMessage)
        session.execute(statement)
        statement = delete(Conversation)
        session.execute(statement)
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
        statement = delete(WalletTransaction)
        session.execute(statement)
        statement = delete(Wallet)
        session.execute(statement)
        statement = delete(Image)
        session.execute(statement)
        statement = delete(ImageCategory)
        session.execute(statement)
        statement = delete(PriceTemplateRule)
        session.execute(statement)
        statement = delete(PriceTemplate)
        session.execute(statement)
        statement = delete(RefreshToken)
        session.execute(statement)
        statement = delete(AutomationTask)
        session.execute(statement)
        statement = delete(AutomationTaskArchive)
        session.execute(statement)
        statement = delete(AutomationEvent)
        session.execute(statement)
        statement = delete(AutomationRule)
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
