"""价格模板初始数据"""

import uuid

from sqlmodel import Session, select

from app.modules.product.category.models import ProductCategory


def seed_product_category_templates(*, session: Session) -> None:
    """商品分类"""

    # 1. 先查询是否已经存在该默认分类（保证幂等性）
    statement = select(ProductCategory).where(ProductCategory.name == "默认分类")
    existing_category = session.exec(statement).first()

    if existing_category:
        print("默认分类已存在，跳过播种。")
        return  # 如果已存在，直接返回，不执行插入

    # 2. 不存在才执行新增
    try:
        new_category = ProductCategory(
            id=uuid.uuid4(),  # 注意：推荐用 uuid4() 生成随机 UUID
            name="默认分类",
            is_active=True,
        )
        session.add(new_category)
        session.commit()
        print("默认分类播种成功！")

    except Exception as e:
        # 3. 发生异常必须回滚，防止 Session 进入脏状态
        session.rollback()
        print(f"播种失败，事务已回滚: {e}")
        raise