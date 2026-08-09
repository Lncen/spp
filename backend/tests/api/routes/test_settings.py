from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.core.redis import get_redis, run_redis_sync
from app.modules.setting.models import AppSetting
from app.modules.setting.service import get_setting
from tests.utils.utils import random_lower_string


def test_get_setting_lazy_loads_default_value(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    """缓存缺失时懒加载：默认设置项无需数据库记录即可读取"""
    run_redis_sync(get_redis().delete("app:settings"))
    r = client.get(
        f"{settings.API_V1_STR}/settings/",
        headers=superuser_token_headers,
    )
    assert r.status_code == 200
    items = {item["key"]: item["value"] for item in r.json()["data"]}
    assert items["maintenance_mode"] is False


def test_setting_update_syncs_cache(
    client: TestClient,
    db: Session,
    superuser_token_headers: dict[str, str],
) -> None:
    """更新设置后，后端内部与前端读取接口均从缓存拿到最新值"""
    key = f"test_setting_{random_lower_string()}"
    try:
        # 清空缓存，验证“缓存未初始化时先更新”也能正确重建完整缓存
        run_redis_sync(get_redis().delete("app:settings"))

        r = client.put(
            f"{settings.API_V1_STR}/settings/{key}",
            headers=superuser_token_headers,
            json={"value": 123},
        )
        assert r.status_code == 200

        assert get_setting(session=db, key=key) == 123

        r = client.get(
            f"{settings.API_V1_STR}/settings/",
            headers=superuser_token_headers,
        )
        assert r.status_code == 200
        items = {item["key"]: item["value"] for item in r.json()["data"]}
        assert items[key] == 123
        # 完整重建后默认设置项也可见
        assert items["maintenance_mode"] is False
    finally:
        row = db.exec(select(AppSetting).where(AppSetting.key == key)).first()
        if row is not None:
            db.delete(row)
            db.commit()
        run_redis_sync(get_redis().delete("app:settings"))
