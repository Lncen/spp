"""系统日志领域规则"""

from app.modules.system_log.domain.event_mapping import (
    SystemLogRecord,
    build_system_log_record,
)

__all__ = ["SystemLogRecord", "build_system_log_record"]
