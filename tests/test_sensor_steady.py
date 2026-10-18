"""The sensor entities publish the steady values, not the raw ones.

Scenario: one Pace pack on RS232 discharges at 906.73 W and its cell 1 flickers
between 3281 mV and 3282 mV. Native units are the upstream ones: kW and mV.
"""

from types import SimpleNamespace

from custom_components.gobel_battery import sensor as sensor_module
from custom_components.gobel_battery.sensor import GobelBatteryCellVoltageSensor, GobelBatteryPackSensor
from fake_hass import make_coordinator


def _coordinator(power_kw, cell_mv):
    coordinator = make_coordinator()
    coordinator.data = {
        "analog": [{"pack_id": 0, "view_power": power_kw, "cell_voltages": [cell_mv]}],
        "warning": [],
    }
    return coordinator


def test_pack_power_is_published_in_kilowatts_to_the_whole_watt():
    coordinator = _coordinator(-0.90673, 3281)
    power = GobelBatteryPackSensor(coordinator, 0, "power", "Power", "kW", None, None, None, None)
    assert power.native_value == -0.907


def test_cell_flicker_is_not_published(monkeypatch):
    clock = SimpleNamespace(now=0.0)
    monkeypatch.setattr(sensor_module, "time", SimpleNamespace(monotonic=lambda: clock.now))
    coordinator = _coordinator(0.0, 3281)
    cell = GobelBatteryCellVoltageSensor(coordinator, 0, 1)
    shown = []
    for poll in range(12):  # one minute of 5 s polls
        coordinator.data["analog"][0]["cell_voltages"] = [3281 if poll % 2 == 0 else 3282]
        shown.append(cell.native_value)
        clock.now += 5
    assert set(shown) == {3281}


def test_cell_voltage_is_published_in_millivolts():
    cell = GobelBatteryCellVoltageSensor(_coordinator(0.0, 3281), 0, 1)
    assert cell.native_unit_of_measurement == "mV"
    assert cell.native_value == 3281
