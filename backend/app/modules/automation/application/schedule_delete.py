"""自动化模块：删除计划任务应用服务"""

from sqlalchemy.orm import Session

from app.modules.automation.repositories.schedule import get_task_or_404


def delete_schedule(*, session: Session, task_id: int) -> None:
    """删除计划任务并清理其 schedule。"""
    task = get_task_or_404(session=session, task_id=task_id)
    schedule_model = task.schedule_model
    session.delete(task)
    if schedule_model is not None:
        session.delete(schedule_model)
    session.commit()
