from typing import TypedDict, Union

class PushMessage(TypedDict):
    title: Union[str, None]
    content: str

class Result(TypedDict):
    success: bool