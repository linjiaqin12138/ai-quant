import json
import logging
import os


class JSONFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps(
            {
                "timestamp": self.formatTime(record),
                "level": record.levelname,
                "message": record.getMessage(),
            }
        )


log_level = getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper())
# file_handler = logging.FileHandler('./quant.log')
# file_handler.setFormatter(JSONFormatter())

console_handler = logging.StreamHandler()
console_handler.setLevel(log_level)
# 设置日志格式，包括时间戳、日志级别和日志信息
console_handler.setFormatter(
    logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
)

logger = logging.getLogger("quant")
logger.setLevel(log_level)
# 将handler添加到logger中
logger.addHandler(console_handler)
# logger.addHandler(file_handler)

__all__ = ["logger"]
