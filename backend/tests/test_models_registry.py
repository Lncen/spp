"""模型注册：保证 Alembic autogenerate 能看到全部表

``app/models.py`` 是 Alembic「env.py」读取 metadata 的聚合入口。
新增模型模块却没有在那里导入时，``alembic revision --autogenerate`` 会静默生成空迁移，
新表永远不会被创建（曾导致运行期 UndefinedTable）。这里做兜底校验。
"""

import importlib
import pkgutil
import sys

import app.models  # noqa: F401  触发模型聚合导入


def _iter_model_module_names() -> set[str]:
    """遍历 app.modules 下所有 models 相关模块"""
    package = importlib.import_module("app.modules")
    return {
        module_info.name
        for module_info in pkgutil.walk_packages(
            package.__path__,
            prefix=f"{package.__name__}.",
        )
        if ".models" in module_info.name
    }


def test_app_models_imports_every_model_module() -> None:
    """每个模型模块都必须被 app.models 导入，否则 autogenerate 会漏表"""
    missing = {
        module_name
        for module_name in _iter_model_module_names()
        if module_name not in sys.modules
    }
    assert missing == set()
