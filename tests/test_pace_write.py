"""Pace write frames match the bytes PBmsTools sends."""

from pace_write import build_pace_request, write_limiter_gear, write_mosfet, write_overcurrent
from pacebms_rs232 import PACEBMS232


class _Comm:
    def __init__(self, response="~250046000000FDAF\r"):
        self.response = response
        self.sent = []

    def flush(self):
        return None

    def send_data(self, data):
        self.sent.append(data)
        return True

    def receive_data(self):
        return self.response


def _bms():
    return PACEBMS232(_Comm(), object(), "PACE_LV", 5, 0, 0)


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
    assert bms.bms_comm.sent[-1] == b"~2500469AE00201FD1D\r"
    assert write_overcurrent(bms, "discharge", 105, 110, 10) is True
    assert b"010069006E0A" in bms.bms_comm.sent[-1]
    assert write_limiter_gear(bms, "high") is True
    assert bms.bms_comm.sent[-1] == b"~25004699E00208FD1E\r"

    bms.bms_comm.response = "~250046010000FD00\r"
    assert write_mosfet(bms, "discharge", False) is False
