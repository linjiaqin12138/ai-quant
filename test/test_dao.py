
from lib.dao import get_all_pairs
from lib.utils.logger import logger


def test_get_all_pairs():
    res = get_all_pairs()
    print(res)

