"""Tests for Pace D9H/DBH current-limit frames."""

from pace_limits import (
    parse_pace_overcurrent_response,
    read_pace_current_limits,
)
from pacebms_rs232 import PACEBMS232
from pacebms_rs485 import PACEBMS485


def _frame(payload):
    info = payload.hex().upper()
    return f"~250046000{len(info):03X}{info}ABCD\r"


class _Comm:
    def __init__(self, responses):
        self.responses = list(responses)
        self.sent = []

    def flush(self):
        return None

    def send_data(self, data):
        self.sent.append(data)
        return True

    def receive_data(self):
        return self.responses.pop(0)


def test_charge_frame_matches_pbms_tools_example():
    # ~25004600400C010068006E0A... is alarm 104 A, protection 110 A.
    parsed = parse_pace_overcurrent_response("~25004600400C010068006E0AFB1D\r", signed=False)
    assert parsed["alarm_a"] == 104
    assert parsed["protection_a"] == 110
    assert parsed["limit_a"] == 110


def test_discharge_frame_is_negative_twos_complement():
    # PBmsTools returns 105 A as FF97 and 110 A as FF92.
    parsed = parse_pace_overcurrent_response("~25004600400C01FF97FF920AFAD3\r", signed=True)
    assert parsed["alarm_a"] == 105
    assert parsed["protection_a"] == 110
    assert parsed["limit_a"] == 110


def test_positive_discharge_encoding_is_also_accepted():
    parsed = parse_pace_overcurrent_response(
        _frame(bytes([1, 0x00, 90, 0x00, 120, 0x00, 80, 5])),
        signed=True,
    )
    assert parsed["limit_a"] == 120


def test_zero_limit_is_rejected():
    assert parse_pace_overcurrent_response(_frame(bytes([1, 0, 0, 0, 0, 0]))) is None
    assert parse_pace_overcurrent_response("not-a-frame") is None


def test_rs232_request_contains_d9_and_db_commands():
    bms = PACEBMS232(object(), object(), "PACE_LV", 5, 0, 0)
    charge = bms.generate_bms_request("charge_overcurrent", 0)
    discharge = bms.generate_bms_request("discharge_overcurrent", 0)
    assert b"D9" in charge
    assert b"DB" in discharge
    assert b"000" in charge


def test_read_limits_sends_both_commands_and_parses_answers():
    comm = _Comm(
        [
            _frame(bytes([1, 0x00, 50, 0x00, 80, 1])),
            _frame(bytes([1, 0x00, 60, 0x00, 100, 0x00, 40, 1])),
        ]
    )
    bms = PACEBMS485(comm, object(), 5, 0, 0)
    limits = read_pace_current_limits(bms, 1)
    assert limits == {
        "view_charge_current_limit": 80,
        "view_charge_current_alarm": 50,
        "view_charge_oc_delay": 1,
        "view_discharge_current_limit": 100,
        "view_discharge_current_alarm": 60,
        "view_discharge_oc_delay": 0,
    }
    assert len(comm.sent) == 2
    assert b"D9" in comm.sent[0]
    assert b"DB" in comm.sent[1]
