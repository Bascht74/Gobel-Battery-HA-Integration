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


def test_charge_frame_uses_protection_amps_as_limit():
    # enable, alarm 80 A, protection 100 A, delay 10
    parsed = parse_pace_overcurrent_response(_frame(bytes([1, 0x00, 80, 0x00, 100, 10])))
    assert parsed["limit_a"] == 100
    assert parsed["alarm_a"] == 80
    assert parsed["enabled"] is True


def test_discharge_frame_ignores_recovery_bytes():
    # enable, alarm 90 A, protection 120 A, recovery 80 A, delay 5
    parsed = parse_pace_overcurrent_response(
        _frame(bytes([1, 0x00, 90, 0x00, 120, 0x00, 80, 5]))
    )
    assert parsed["limit_a"] == 120
    assert parsed["protection_a"] == 120


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
        "view_discharge_current_limit": 100,
    }
    assert len(comm.sent) == 2
    assert b"D9" in comm.sent[0]
    assert b"DB" in comm.sent[1]
