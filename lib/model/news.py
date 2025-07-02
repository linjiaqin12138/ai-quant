from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Dict, Optional


@dataclass
class NewsInfo:
    news_id: str
    title: str
    timestamp: datetime
    url: str
    platform: str

    description: Optional[str] = None

    def to_dict(self):
        # 使用dataclasses.asdict()获取字典表示
        data_dict = asdict(self)
        # 将timestamp字to_段从datetime对象转换为时间戳
        data_dict["timestamp"] = int(self.timestamp.timestamp() * 1000)
        return data_dict

    @classmethod
    def from_dict(cls, data_dict: Dict):
        """
        从包含时间戳（数字时间戳）的字典中初始化Ohlcv对象。

        :param data_dict: 包含时间戳的字典
        :return: Ohlcv对象
        """
        # 将数字时间戳转换回datetime对象
        timestamp_dt = datetime.fromtimestamp(data_dict["timestamp"] / 1000)
        # 创建Ohlcv对象
        return cls(
            timestamp=timestamp_dt,
            title=data_dict["title"],
            news_id=data_dict["news_id"],
            url=data_dict["url"],
            platform=data_dict["platform"],
            description=data_dict.get("description", None),
            reason=data_dict.get("reason", None),
            mood=data_dict.get("mood", None),
        )
