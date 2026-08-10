"""自动化模块：任务执行领域规则"""


def should_retry(*, retry_count: int, max_retry: int) -> bool:
    """失败后是否允许重试：已重试次数未达上限。"""
    return retry_count < max_retry
