"""Values that only flicker or tick must not fill the recorder.

Home Assistant stores a row for every state change. The integration polls every 5 s.
The real numbers behind these tests come from the user's history of 17/18 Oct 2026:
cell 9 of pack 1 changed 117 times in 10 hours, and the BMS clock 851 times.
"""

from datetime import datetime, timedelta

from custom_components.gobel_battery.steady import (
    CLOCK_REFRESH_SECONDS,
    STEP_HOLD_SECONDS,
    ClockHold,
    StepHold,
    rounded,
)

POLL = 5  # seconds between two reads


def _show(hold, values):
    """Feed one value per 5 s poll and return what the entity shows after each poll."""
    return [hold.update(value, poll * POLL) for poll, value in enumerate(values)]


def test_a_cell_that_flickers_by_one_millivolt_stays_put():
    # 3.281 V and 3.282 V take turns for 2 minutes: nothing new to store.
    cell = StepHold(0.001)
    shown = _show(cell, [3.281, 3.282] * 12)
    assert set(shown) == {3.281}


def test_a_one_millivolt_change_shows_after_a_minute():
    # The cell moves from 3.281 V to 3.282 V and stays there.
    assert STEP_HOLD_SECONDS == 60
    cell = StepHold(0.001)
    shown = _show(cell, [3.281] + [3.282] * 14)
    # Poll 1 sees the new value at 5 s; 60 s later, at poll 13, it is shown.
    assert shown[12] == 3.281
    assert shown[13] == 3.282


def test_a_change_of_two_millivolts_or_more_shows_at_once():
    # Charging starts: the cell jumps from 3.281 V to 3.290 V.
    cell = StepHold(0.001)
    assert _show(cell, [3.281, 3.290]) == [3.281, 3.290]


def test_a_missing_value_is_passed_on():
    pack_voltage = StepHold(0.01)
    assert _show(pack_voltage, [52.10, None, 52.11]) == [52.10, None, 52.11]


def test_power_is_whole_watts_and_energy_is_ten_watt_hours():
    # 52.31 V x 17.33 A = 906.53 W. The tenths come from rounding V and A, not from the BMS.
    assert rounded(906.5323, 0) == 907.0
    # The counter grows 1.25 Wh per 5 s at 900 W: shown in 0.01 kWh it changes every 40 s.
    assert rounded(0.04425, 2) == 0.04
    assert rounded(None, 2) is None


START = datetime(2026, 10, 18, 8, 0, 0)


def _stamp(moment):
    return f"{moment:%Y-%m-%d %H:%M:%S}"


def test_a_ticking_bms_clock_is_shown_again_after_15_minutes():
    # The BMS clock runs 2 s ahead and is read once a minute.
    assert CLOCK_REFRESH_SECONDS == 15 * 60
    clock = ClockHold()
    shown = []
    for minute in range(16):
        now = START + timedelta(minutes=minute)
        shown.append(clock.update(_stamp(now + timedelta(seconds=2)), now))
    assert shown[:15] == ["2026-10-18 08:00:02"] * 15
    assert shown[15] == "2026-10-18 08:15:02"


def test_a_bms_clock_that_was_set_shows_at_once():
    # The clock was 6 hours behind; the button sets it to the Home Assistant time.
    clock = ClockHold()
    clock.update(_stamp(START - timedelta(hours=6)), START)
    after_set = START + timedelta(minutes=1)
    assert clock.update(_stamp(after_set), after_set) == "2026-10-18 08:01:00"
