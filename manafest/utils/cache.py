import json


def read_registry(path):
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def write_registry(path, data):
    path.write_text(json.dumps(data, indent=2))
