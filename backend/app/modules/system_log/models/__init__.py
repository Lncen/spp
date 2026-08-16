"""系统日志数据模型"""

from app.modules.system_log.models.audit_log import AuditLog
from app.modules.system_log.models.system_log import SystemLog

__all__ = ["AuditLog", "SystemLog"]
