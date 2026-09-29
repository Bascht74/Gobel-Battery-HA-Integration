"""Tests for unit conversion, SOC fallback and energy counters."""

from measurements import (
    bms_throughput_kwh,
    integrate_energy_kwh,
    kwh_from_amp_hours,
    present_temperatures,
    resolve_soc,
    resolve_soh,
    volts_from_millivolts,
    watts_from_kilowatts,
)


def test_cell_voltage_is_volts_with_three_decimals():
    assert volts_from_millivolts(3321) == 3.321
    assert volts_from_millivolts(None) is None


def test_power_is_converted_from_kilowatts_to_watts():
    assert watts_from_kilowatts(1.25) == 1250.0
    assert watts_from_kilowatts(-0.5) == -500.0


def test_unfitted_probe_keeps_the_other_slot_numbers():
    slots = present_temperatures([25.3, 24.1, 26.0, 25.0, -273.15, 31.2])
    assert slots == [25.3, 24.1, 26.0, 25.0, None, 31.2]
    assert present_temperatures([21.0, 22.0, 23.0, 24.0, 25.0, 26.0])[4:] == [25.0, 26.0]


def test_amp_hours_become_kwh_with_fixed_cell_voltage():
    # 100 Ah * 16 cells * 3.2 V = 5120 Wh = 5.12 kWh
    assert kwh_from_amp_hours(100, 16) == 5.12
    assert kwh_from_amp_hours(100, 0) is None


def test_soc_above_100_uses_capacity_ratio():
    assert resolve_soc(226, 70.8, 100) == 70.8
    assert resolve_soc(66, 66, 100) == 66.0
    assert resolve_soc(None, 25, 50) == 50.0


def test_soh_zero_uses_full_over_design():
    assert resolve_soh(0, 95, 100) == 95.0
    assert resolve_soh(98, 95, 100) == 98.0
    assert resolve_soh(None, 90, 100) == 90.0


def test_copied_design_capacity_is_not_treated_as_throughput():
    assert bms_throughput_kwh(100, 100, 16, 100) is None
    assert bms_throughput_kwh(2500, 1800, 16, 100) == 128.0


def test_integrated_energy_adds_kwh_and_ignores_long_gaps():
    charged, discharged = integrate_energy_kwh(1.0, 0.5, 3600, 60)
    assert round(charged, 3) == 1.06
    assert discharged == 0.5

    charged, discharged = integrate_energy_kwh(1.0, 0.0, -500, 60)
    assert charged == 1.0
    assert round(discharged, 4) == 0.0083

    charged, discharged = integrate_energy_kwh(1.0, 0.2, 5000, 301)
    assert (charged, discharged) == (1.0, 0.2)
