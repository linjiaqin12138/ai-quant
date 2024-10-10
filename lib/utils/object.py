
def remove_none(obj: dict)->dict:
    return {k: v for k, v in obj.items() if v is not None}