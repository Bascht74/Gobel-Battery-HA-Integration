"""The setup probe must not confuse a pushed frame with a command reply."""

from pace_probe import ACTIVE, PASSIVE, SILENT, COMMON_TCP_PORTS, classify_pace_traffic


def test_command_reply_is_active_even_if_the_bms_also_pushes():
    before = b"~2500464200100000FD00\r"
    after = b"~250046000000FDAF\r"
    assert classify_pace_traffic(before, after) == ACTIVE


def test_unsolicited_analog_frame_is_passive():
    pushed = b"~25004642F0100100000000FD00\r"
    assert classify_pace_traffic(pushed, b"") == PASSIVE
    assert classify_pace_traffic(b"", pushed) == PASSIVE


def test_dongle_heartbeat_is_passive():
    assert classify_pace_traffic(b"gobel\r", b"") == PASSIVE


def test_no_bytes_is_silent():
    assert classify_pace_traffic(b"", b"") == SILENT


def test_standard_ports_are_gobel_then_hiflying():
    assert COMMON_TCP_PORTS == (9999, 8899)
