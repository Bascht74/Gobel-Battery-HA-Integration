"""Switching the changeable-settings option removes the entities of the other mode.

Example: on RS232 only pack 0 (the master on the cable) has settings that can
be written. "cell_ov_alarm" is one Pace setting; "soc" is a measurement.
"""

from mode_cleanup import stale_unique_ids

ENTRY = "abc"


def only_master(pack_id):
    return pack_id == 0


def test_changeable_mode_removes_the_read_only_copy_of_a_setting():
    stale = stale_unique_ids(ENTRY, ["abc_pack_0_cell_ov_alarm"], True, only_master)
    assert stale == {"abc_pack_0_cell_ov_alarm"}


def test_changeable_mode_removes_the_charge_flag_that_a_switch_replaces():
    flag = "abc_pack_0_instruction_state_status_charge_enabled"
    assert stale_unique_ids(ENTRY, [flag], True, only_master) == {flag}


def test_changeable_mode_keeps_the_charge_flag_of_a_pack_without_switch():
    flag = "abc_pack_1_instruction_state_status_charge_enabled"
    assert stale_unique_ids(ENTRY, [flag], True, only_master) == set()


def test_read_mode_removes_the_changeable_entities():
    ids = ["abc_pack_0_expert_cell_ov_alarm", "abc_pack_0_expert_charge_switch"]
    assert stale_unique_ids(ENTRY, ids, False, only_master) == set(ids)


def test_read_mode_keeps_the_read_only_setting_sensors():
    assert stale_unique_ids(ENTRY, ["abc_pack_0_cell_ov_alarm"], False, only_master) == set()


def test_measurements_stay_in_both_modes():
    ids = ["abc_pack_0_soc", "abc_pack_0_cell_1_voltage", "abc_total_soc", "abc_pack_0_bms_clock"]
    assert stale_unique_ids(ENTRY, ids, True, only_master) == set()
    assert stale_unique_ids(ENTRY, ids, False, only_master) == set()


def test_entities_of_another_entry_are_left_alone():
    assert stale_unique_ids(ENTRY, ["xyz_pack_0_expert_charge_switch"], False, only_master) == set()
