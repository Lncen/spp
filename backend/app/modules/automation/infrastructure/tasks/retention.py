"""自动化模块：定时任务保留期读取辅助"""

from sqlmodel import Session

from app.modules.setting.application.setting_query import get_setting


def get_retention_days(*, session: Session, key: str, default: int) -> int:
    """读取全局设置中的保留天数，非法值回退默认值，最少保留 1 天。"""
    try:
        days = int(get_setting(session=session, key=key))
    except (TypeError, ValueError):
        return default
    return max(1, days)
