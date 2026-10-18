"""hassfest accepts only lower-case translation keys, for example "fault_ntc", not "fault_NTC"."""

import json
import re
from pathlib import Path

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "gobel_battery"
FILES = [COMPONENT / "strings.json", *sorted((COMPONENT / "translations").glob("*.json"))]
VALID_KEY = re.compile(r"^[a-z0-9]([a-z0-9_-]*[a-z0-9])?$")


def _keys(node, path=""):
    """Every key of the nested JSON, with its path for a readable failure."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield f"{path}/{key}", key
            yield from _keys(value, f"{path}/{key}")


def test_all_translation_keys_are_lower_case():
    bad = [
        f"{file.name}:{path}"
        for file in FILES
        for path, key in _keys(json.loads(file.read_text()))
        if not VALID_KEY.match(key)
    ]
    assert bad == []
