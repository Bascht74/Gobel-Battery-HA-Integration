"""Pace write frames match the bytes PBmsTools sends."""

from datetime import datetime

from custom_components.gobel_battery.pace_write import build_pace_request, write_buzzer, write_limiter_gear, write_mosfet, write_overcurrent
from custom_components.gobel_battery.pacebms_rs232 import PACEBMS232


class _Comm:
    def __init__(self, response="~250046000000FDAF\r"):
        self.response = response
        self.sent = []

    def flush(self):
        return None

    def send_data(self, data):
        self.sent.append(data)
        return True

    def receive_data(self, timeout=None):
        return self.response


def _bms():
    return PACEBMS232(_Comm(), object(), "PACE_LV", 5, 0, 0)


def test_clock_write_matches_the_protocol_example():
    bms = _bms()
    moment = datetime(2024, 8, 20, 14, 15, 37)
    payload = bytes([24, 8, 20, 14, 15, 37]).hex().upper()
    assert build_pace_request(bms, "B2", payload) == b"~250046B2400C1808140E0F25FAFC\r"
    assert moment.year - 2000 == 24
    bms = _bms()
    assert build_pace_request(bms, "99", "0C") == b"~25004699E0020CFD13\r"
    assert build_pace_request(bms, "99", "0D") == b"~25004699E0020DFD12\r"
    assert build_pace_request(bms, "99", "07") == b"~25004699E00207FD1F\r"
    assert build_pace_request(bms, "99", "06") == b"~25004699E00206FD20\r"


def test_charge_mosfet_frames_match_pbms_tools():
    bms = _bms()
    assert build_pace_request(bms, "9A", "00") == b"~2500469AE00200FD1E\r"
    assert build_pace_request(bms, "9A", "01") == b"~2500469AE00201FD1D\r"


def test_charge_protection_is_written_as_positive_amps():
    bms = _bms()
    frame = build_pace_request(bms, "D8", "010068006E0A")
    assert frame == b"~250046D8400C010068006E0AFB01\r"


def test_discharge_protection_is_written_positive_not_twos_complement():
    bms = _bms()
    frame = build_pace_request(bms, "DA", "010069006E0A")
    assert frame == b"~250046DA400C010069006E0AFAF7\r"
    assert b"FF92" not in frame


def test_write_helpers_only_accept_a_successful_response():
    bms = _bms()
    assert write_mosfet(bms, "charge", True) is True
    assert bms.bms_comm.sent[-1] == b"~2500469AE00200FD1E\r"
    assert write_overcurrent(bms, "discharge", 105, 110, 10) is True
    assert b"010069006E0A" in bms.bms_comm.sent[-1]
    assert write_limiter_gear(bms, "high") is True
    assert bms.bms_comm.sent[-1] == b"~25004699E00208FD1E\r"

    bms.bms_comm.response = "~250046010000FD00\r"
    assert write_mosfet(bms, "discharge", False) is False


def test_switching_a_mosfet_on_sends_00_and_off_sends_01():
    # Protocol doc 9AH/9BH: 00 = on, 01 = off. A PBmsTools capture shows 9A 01
    # clearing the charge-MOSFET bit.
    bms = _bms()
    write_mosfet(bms, "charge", True)
    assert bms.bms_comm.sent[-1] == b"~2500469AE00200FD1E\r"
    write_mosfet(bms, "charge", False)
    assert bms.bms_comm.sent[-1] == b"~2500469AE00201FD1D\r"


def test_switching_the_buzzer_on_sends_0d():
    bms = _bms()
    write_buzzer(bms, True)
    assert bms.bms_comm.sent[-1] == b"~25004699E0020DFD12\r"
    write_buzzer(bms, False)
    assert bms.bms_comm.sent[-1] == b"~25004699E0020CFD13\r"
