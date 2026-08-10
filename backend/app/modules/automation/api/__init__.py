"""自动化模块：接口层"""

from app.modules.automation.api.automation import router as automation_router
from app.modules.automation.api.events import router as automation_events_router
from app.modules.automation.api.rules import router as automation_rules_router
from app.modules.automation.api.schedules import router as schedule_router
from app.modules.automation.api.tasks import router as schedule_tasks_router

__all__ = [
    "automation_events_router",
    "automation_rules_router",
    "automation_router",
    "schedule_router",
    "schedule_tasks_router",
]
