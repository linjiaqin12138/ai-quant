import requests
from typing import List

def get_china_holiday(year: str) -> List[str]:
    return list(requests.get(f"https://api.jiejiariapi.com/v1/holidays/{year}").json().keys())

