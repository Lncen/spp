"""价格模板模块：路由层。函数名保持不变以保证 OpenAPI operationId 兼容性"""

import uuid
from typing import Any

from fastapi import APIRouter, Depends

from app.api.deps import SessionDep, require_permission
from app.common.models import Message
from app.modules.price_template.models import PriceTemplate, PriceTemplateRule
from app.modules.price_template.schemas import (
    PriceTemplateCreate,
    PriceTemplatePublic,
    PriceTemplateRulePublic,
    PriceTemplatesPublic,
    PriceTemplateUpdate,
)
from app.modules.price_template.service import (
    create_price_template as create_price_template_service,
)
from app.modules.price_template.service import (
    delete_price_template as delete_price_template_service,
)
from app.modules.price_template.service import (
    get_all_price_templates,
    get_price_template,
    get_price_template_count,
    get_rules_by_template_id,
    get_rules_by_template_ids,
)
from app.modules.price_template.service import (
    update_price_template as update_price_template_service,
)

router = APIRouter(prefix="/price-templates", tags=["price-templates"])


def _rule_to_public(rule: PriceTemplateRule, level: int) -> PriceTemplateRulePublic:
    """将 PriceTemplateRule 转换为 PriceTemplateRulePublic"""
    return PriceTemplateRulePublic(
        id=rule.id,
        level=level,
        discount_rate=rule.discount_rate,
    )


def _template_to_public(
    template: PriceTemplate,
    rules: list[tuple[PriceTemplateRule, int]],
) -> PriceTemplatePublic:
    """将 PriceTemplate 转换为 PriceTemplatePublic（含规则）"""
    return PriceTemplatePublic(
        id=template.id,
        name=template.name,
        description=template.description,
        is_default=template.is_default,
        is_active=template.is_active,
        created_at=template.created_at,
        updated_at=template.updated_at,
        rules=[_rule_to_public(rule, level) for rule, level in rules],
    )


@router.get(
    "/",
    dependencies=[Depends(require_permission("price_template:view"))],
    response_model=PriceTemplatesPublic,
)
def read_price_templates(
    session: SessionDep, skip: int = 0, limit: int = 100
) -> Any:
    """获取价格模板列表"""
    templates = get_all_price_templates(session=session, skip=skip, limit=limit)
    count = get_price_template_count(session=session)
    rules_map = get_rules_by_template_ids(
        session=session,
        template_ids=[template.id for template in templates],
    )
    return PriceTemplatesPublic(
        data=[
            _template_to_public(template, rules_map.get(template.id, []))
            for template in templates
        ],
        count=count,
    )


@router.post(
    "/",
    dependencies=[Depends(require_permission("price_template:create"))],
    response_model=PriceTemplatePublic,
)
def create_price_template(
    *, session: SessionDep, template_in: PriceTemplateCreate
) -> Any:
    """创建价格模板（缺失等级自动补 15 折）"""
    template = create_price_template_service(session=session, template_in=template_in)
    rules = get_rules_by_template_id(session=session, template_id=template.id)
    return _template_to_public(template, rules)


@router.get(
    "/{template_id}",
    dependencies=[Depends(require_permission("price_template:view"))],
    response_model=PriceTemplatePublic,
)
def read_price_template(session: SessionDep, template_id: uuid.UUID) -> Any:
    """获取价格模板详情"""
    template = get_price_template(session=session, template_id=template_id)
    rules = get_rules_by_template_id(session=session, template_id=template_id)
    return _template_to_public(template, rules)


@router.put(
    "/{template_id}",
    dependencies=[Depends(require_permission("price_template:update"))],
    response_model=PriceTemplatePublic,
)
def update_price_template(
    *,
    session: SessionDep,
    template_id: uuid.UUID,
    template_in: PriceTemplateUpdate,
) -> Any:
    """更新价格模板（传入的等级折扣将覆盖，未传等级保留）"""
    template = update_price_template_service(
        session=session,
        template_id=template_id,
        template_in=template_in,
    )
    rules = get_rules_by_template_id(session=session, template_id=template.id)
    return _template_to_public(template, rules)


@router.delete(
    "/{template_id}",
    dependencies=[Depends(require_permission("price_template:delete"))],
    response_model=Message,
)
def delete_price_template(session: SessionDep, template_id: uuid.UUID) -> Message:
    """删除价格模板（规则级联删除）"""
    delete_price_template_service(session=session, template_id=template_id)
    return Message(message="价格模板已删除")
