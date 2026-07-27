import logging

from sqlmodel import Session

from app import models  # noqa: F401 — 确保所有 SQLModel 模型在 init_db 前注册
from app.core.db import engine, init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init() -> None:
    with Session(engine) as session:
        init_db(session)


def main() -> None:
    logger.info("创建初始数据")
    init()
    logger.info("创建初始数据")


if __name__ == "__main__":
    main()
