
import random
import string

def random_id(length: int) -> str:
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))
