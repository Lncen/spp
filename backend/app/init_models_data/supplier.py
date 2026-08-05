import uuid
from sqlmodel import Session, select
from app.modules.supplier.models import Supplier


def seed_supplier_templates(*, session: Session) -> None:
    """播种默认供应商模板，幂等安全（已存在则跳过）"""

    # 1. 根据唯一业务键（如 name）查询是否已存在
    statement = select(Supplier).where(Supplier.name == "buer")
    existing_supplier = session.exec(statement).first()

    if existing_supplier:
        print("供应商 'buer' 已存在，跳过播种。")
        return

    # 2. 不存在才执行新增
    try:
        new_supplier = Supplier(
            id=uuid.uuid4(),  # ✅ 关键修正：必须使用 uuid4() 生成随机 UUID
            name="buer",
            platform="ylsup",
            base_url="https://fhnt.club",
            app_key="4a0357341c6c0c220266672570937c9a",
            app_secret="5468fd321edac451c24c34b611720c904fe595c7",
        )
        session.add(new_supplier)
        session.commit()
        print("供应商 'buer' 播种成功！")

    except Exception as e:
        # 3. 发生异常必须回滚，防止 Session 脏状态
        session.rollback()
        print(f"播种失败，事务已回滚: {e}")
        raise