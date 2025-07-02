import json
import logging
from typing import Optional

from lib.config import get_log_level


class JSONFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps(
            {
                "timestamp": self.formatTime(record),
                "level": record.levelname,
                "message": record.getMessage(),
            }
        )


console_handler = logging.StreamHandler()
console_handler.setLevel(getattr(logging, get_log_level()))
# 设置日志格式，包括时间戳、日志级别和日志信息
console_handler.setFormatter(
    logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
)

file_handlers = {}


def create_logger(
    name: str,
    *,
    level: int = logging.DEBUG,
    log_file: Optional[str] = None,
) -> logging.Logger:
    """
    创建一个新的logger实例
    :param name: logger的名称
    :param level: 日志文件日志级别
    :param log_file: 日志文件路径
    :return: logger实例
    """
    logger = logging.getLogger(name)
    # 设置日志级别比debug还低，由console_handler控制输出
    logger.setLevel(5)
    logger.propagate = False
    logger.addHandler(console_handler)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(JSONFormatter())
        file_handler.setLevel(level)
        logger.addHandler(file_handler)
    return logger


logger = create_logger("quant")

__all__ = ["logger", "create_logger"]
