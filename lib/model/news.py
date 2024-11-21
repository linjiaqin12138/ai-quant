from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class NewsInfo:
    news_id: str
    title: str
    timestamp: datetime
    url: str
    platform: str

    description: Optional[str] = None
    reason: Optional[str] = None
    mood: Optional[float] = None