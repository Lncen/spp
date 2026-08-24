"""统一时间工具：全项目时间统一使用中国时区（Asia/Shanghai）记录"""

from datetime import datetime
from zoneinfo import ZoneInfo

CN_TZ = ZoneInfo("Asia/Shanghai")


def get_datetime_cn() -> datetime:
    """获取当前北京时间（UTC+8，带时区信息的 aware datetime）"""
    return datetime.now(CN_TZ)
