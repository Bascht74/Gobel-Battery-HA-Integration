"""The modules load the way Home Assistant loads them: as one package with relative imports."""

import importlib


def test_coordinator_and_platforms_import_as_a_package():
    for name in ("coordinator", "config_flow", "sensor", "binary_sensor", "number", "switch", "select", "button"):
        module = importlib.import_module(f"custom_components.gobel_battery.{name}")
        assert module.__package__ == "custom_components.gobel_battery"
