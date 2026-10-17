"""Home Assistant refuses a sensor or binary sensor with the config category.

It logs "cannot be added as the entity category is set to config" and the
entity never appears. Only entities that can be changed (number, switch,
select, button) may use it.
"""

import ast
from pathlib import Path

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "gobel_battery"


def uses_config_category(file_name):
    tree = ast.parse((COMPONENT / file_name).read_text())
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and node.attr == "CONFIG"
        and isinstance(node.value, ast.Name)
        and node.value.id == "EntityCategory"
    ]


def test_sensors_do_not_use_the_config_category():
    assert uses_config_category("sensor.py") == []


def test_binary_sensors_do_not_use_the_config_category():
    assert uses_config_category("binary_sensor.py") == []
