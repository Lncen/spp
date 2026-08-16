"""系统日志数据访问层"""

from app.modules.system_log.repositories.audit_log import (
    count_audit_logs,
    create_audit_log,
    get_audit_log_or_404,
    list_audit_logs,
)
from app.modules.system_log.repositories.system_log import (
    count_system_logs,
    create_system_log,
    get_system_log_or_404,
    list_system_logs,
)

__all__ = [
    "count_audit_logs",
    "count_system_logs",
    "create_audit_log",
    "create_system_log",
    "get_audit_log_or_404",
    "get_system_log_or_404",
    "list_audit_logs",
    "list_system_logs",
]
