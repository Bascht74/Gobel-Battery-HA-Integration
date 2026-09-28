"""JK power is unsigned in the frame and must follow the current sign."""

import logging
import struct

from jkbms_rs485 import JKBMS485


def _parser():
    parser = JKBMS485.__new__(JKBMS485)
    parser.logger = logging.getLogger("jk-test")
    return parser


def _frame(power_mw, current_ma):
    data = bytearray(170)
    data[0] = 0x55
    data[1] = 0xAA
    struct.pack_into("<I", data, 154, power_mw)
    struct.pack_into("<i", data, 158, current_ma)
    return bytes(data)


def test_discharge_power_is_negative_when_current_is_negative():
    parsed = _parser().parse_jkbms_55aa_frame(_frame(2_500_000, -40_000))
    assert parsed["current_a"] == -40.0
    assert parsed["power_kw"] == -2.5


def test_charge_power_stays_positive():
    parsed = _parser().parse_jkbms_55aa_frame(_frame(1_000_000, 20_000))
    assert parsed["current_a"] == 20.0
    assert parsed["power_kw"] == 1.0
