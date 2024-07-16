import json

def read_json_file(path: str) -> dict:
    with open(path, 'r') as file:
        return json.loads(file.read())