"""Pace settings are read a few groups per poll, each group once per round.

There are 19 groups and 4 are read per poll, so a round takes 5 polls:
4 + 4 + 4 + 4 + 3. After a round the reads pause until LIMIT_POLL_SECONDS have passed.
"""

from custom_components.gobel_battery import coordinator as coordinator_module
from custom_components.gobel_battery.pace_config import GROUPS, GROUPS_PER_POLL
from custom_components.gobel_battery.pacebms_rs232 import PACEBMS232
from fake_hass import make_coordinator


def test_one_round_reads_every_group_once_then_pauses(monkeypatch):
    assert (len(GROUPS), GROUPS_PER_POLL) == (19, 4)
    slices = []

    def read_slice(_bms, start, count, pack_number=None):
        slices.append((start, count))
        return {}, {}

    monkeypatch.setattr(coordinator_module, "read_configuration_slice", read_slice)
    coordinator = make_coordinator()
    coordinator.bms = PACEBMS232(None, object(), "PACE_LV", 5, 0, 0)
    coordinator._config_cache["all"] = {"cursor": 0, "values": {"view_cell_ov_alarm": 3.6}, "raw": {}, "ts": 0}

    for _poll in range(6):
        coordinator._attach_current_limits([{"pack_id": 0}])

    assert slices == [(0, 4), (4, 4), (8, 4), (12, 4), (16, 3)]
    assert coordinator.config_rounds == 1


def test_a_round_without_any_answer_does_not_count_for_the_cleanup(monkeypatch):
    # The TCP serial server is busy (PBmsTools holds it): every settings read in the round
    # times out. That says nothing about which settings the BMS has, so no entity may go.
    monkeypatch.setattr(coordinator_module, "read_configuration_slice", lambda *_a, **_k: ({}, {}))
    coordinator = make_coordinator()
    coordinator.bms = PACEBMS232(None, object(), "PACE_LV", 5, 0, 0)

    for _poll in range(5):  # one full round of 5 polls
        coordinator._attach_current_limits([{"pack_id": 0}])

    assert coordinator.config_rounds == 1
    assert coordinator.config_round_results == {}


def test_a_round_with_answers_counts_for_the_cleanup(monkeypatch):
    # Only the first group (cell overvoltage) answers; the other groups stay empty.
    def read_slice(_bms, start, count, pack_number=None):
        return ({"view_cell_ov_alarm": 3.6}, {}) if start == 0 else ({}, {})

    monkeypatch.setattr(coordinator_module, "read_configuration_slice", read_slice)
    coordinator = make_coordinator()
    coordinator.bms = PACEBMS232(None, object(), "PACE_LV", 5, 0, 0)

    for _poll in range(5):
        coordinator._attach_current_limits([{"pack_id": 0}])

    assert coordinator.config_round_results == {"all": (1, {"view_cell_ov_alarm"})}
