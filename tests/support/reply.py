import json


def reply(engine_name: str) -> str:
    """A one-hit JSON reply a fake search engine returns."""
    return json.dumps([{"id": f"{engine_name}-1", "title": f"hit from {engine_name}"}])
