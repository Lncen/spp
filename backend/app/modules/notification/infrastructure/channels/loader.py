"""渠道加载器：显式导入渠道模块以触发注册（注册副作用不入 __init__.py）"""


def load_channels() -> None:
    """导入全部内置渠道模块，幂等（Python 模块缓存保证）"""
    from app.modules.notification.infrastructure.channels import (  # noqa: F401
        email,
        in_app,
    )
