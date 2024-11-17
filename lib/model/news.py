from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class NewsInfo:
    news_id: str
    title: str
    description: Optional[str]
    timestamp: datetime
    url: str
    platform: str

    reason: Optional[str]
    mood: Optional[float]