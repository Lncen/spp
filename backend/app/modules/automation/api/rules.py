"""自动化模块：规则路由"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import SessionDep, get_current_active_superuser
from app.common.models import Message
from app.modules.automation.application.rule import (
    create_automation_rule as create_automation_rule_service,
)
from app.modules.automation.application.rule import (
    delete_automation_rule as delete_automation_rule_service,
)
from app.modules.automation.application.rule import (
    get_automation_rule_public,
    list_automation_rules,
)
from app.modules.automation.application.rule import (
    toggle_automation_rule as toggle_automation_rule_service,
)
from app.modules.automation.application.rule import (
    update_automation_rule as update_automation_rule_service,
)
from app.modules.automation.schemas import (
    AutomationRuleCreate,
    AutomationRulePublic,
    AutomationRulesPublic,
    AutomationRuleUpdate,
)

router = APIRouter(prefix="/automation/rules", tags=["automation"])


@router.get(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=AutomationRulesPublic,
)
def read_automation_rules(
    session: SessionDep,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
) -> Any:
    """获取自动化规则列表（超管权限）"""
    return list_automation_rules(session=session, skip=skip, limit=limit)


@router.post(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=AutomationRulePublic,
)
def create_automation_rule(
    *,
    session: SessionDep,
    rule_in: AutomationRuleCreate,
) -> Any:
    """创建自动化规则（超管权限）"""
    try:
        rule = create_automation_rule_service(session=session, rule_in=rule_in)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return get_automation_rule_public(session=session, rule_id=rule.id)


@router.get(
    "/{id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=AutomationRulePublic,
)
def read_automation_rule(
    session: SessionDep,
    id: uuid.UUID,
) -> Any:
    """根据 ID 获取自动化规则（超管权限）"""
    return get_automation_rule_public(session=session, rule_id=id)


@router.put(
    "/{id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=AutomationRulePublic,
)
def update_automation_rule(
    *,
    session: SessionDep,
    id: uuid.UUID,
    rule_in: AutomationRuleUpdate,
) -> Any:
    """更新自动化规则（超管权限）"""
    try:
        rule = update_automation_rule_service(
            session=session,
            rule_id=id,
            rule_in=rule_in,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    return get_automation_rule_public(session=session, rule_id=rule.id)


@router.post(
    "/{id}/toggle",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=AutomationRulePublic,
)
def toggle_automation_rule(
    session: SessionDep,
    id: uuid.UUID,
) -> Any:
    """启用或停用自动化规则（超管权限）"""
    toggle_automation_rule_service(session=session, rule_id=id)
    return get_automation_rule_public(session=session, rule_id=id)


@router.delete(
    "/{id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=Message,
)
def delete_automation_rule(
    session: SessionDep,
    id: uuid.UUID,
) -> Message:
    """删除自动化规则（超管权限）"""
    delete_automation_rule_service(session=session, rule_id=id)
    return Message(message="自动化规则已删除")
