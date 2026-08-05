import uuid
from sqlmodel import Session, select
from app.modules.supplier.models import Supplier

def seed_supplier_templates(*, session: Session) -> None:
    """播种默认供应商模板，幂等安全（已存在则跳过）"""

    # 定义要播种的供应商列表
    suppliers_to_seed = [
        {
            "name": "自营",
            "platform": "self",
            "base_url": "httub",
            "app_key": "4a03572570937c9a",
            "app_secret": "5c34b61595c7"
        },
        {
            "name": "buer",
            "platform": "ylsup",
            "base_url": "https://fhnt.club",
            "app_key": "4a0357341c6c0c220266672570937c9a",
            "app_secret": "5468fd321edac451c24c34b611720c904fe595c7",
        }
    ]

    added_count = 0
    try:
        for supplier_data in suppliers_to_seed:
            # 针对每一个供应商单独查询是否存在
            statement = select(Supplier).where(Supplier.name == supplier_data["name"])
            existing_supplier = session.exec(statement).first()

            if existing_supplier:
                print(f"供应商 '{supplier_data['name']}' 已存在，跳过。")
                continue

            # 不存在则新增
            new_supplier = Supplier(
                id=uuid.uuid4(),
                **supplier_data  # 使用字典解包传入参数，代码更简洁
            )
            session.add(new_supplier)
            added_count += 1

        # 统一提交事务
        if added_count > 0:
            session.commit()
            print(f"成功播种了 {added_count} 个新供应商！")
        else:
            print("没有需要播种的新供应商。")

    except Exception as e:
        session.rollback()
        print(f"播种失败，事务已回滚: {e}")
        raise