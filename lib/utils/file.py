import json


def read_json_file(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as file:
        return json.loads(file.read())
