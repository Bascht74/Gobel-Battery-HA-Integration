"""Pace configuration frames match the PBmsTools examples."""

from pace_config import GROUPS, decode_group, encode_group, info_payload, read_group, write_frame
from pacebms_rs232 import PACEBMS232


class _Comm:
    def flush(self):
        return None

    def send_data(self, data):
        return True

    def receive_data(self):
        return None


def _bms():
    return PACEBMS232(_Comm(), object(), "PACE_LV", 5, 0, 0)


EXAMPLES = {
    "cell_ov": (
        "~25004600F010010E100E740D340AFA35\r",
        "~250046D0F010010E100E740D340AFA21\r",
        {"view_cell_ov_alarm": 3.6, "view_cell_ov_protect": 3.7, "view_cell_ov_release": 3.38, "view_cell_ov_delay": 1000},
    ),
    "pack_ov": (
        "~25004600F01001E100E740D2F00AFA24\r",
        "~250046D4F01001E10AE740D2F00AF9FB\r",
        {"view_pack_ov_alarm": 57.6, "view_pack_ov_protect": 59.2, "view_pack_ov_release": 54.0, "view_pack_ov_delay": 1000},
    ),
    "cell_uv": (
        "~25004600F010010AF009C40B540AFA24\r",
        "~250046D2F010010AF009C40B540AFA0E\r",
        {"view_cell_uv_alarm": 2.8, "view_cell_uv_protect": 2.5, "view_cell_uv_release": 2.9, "view_cell_uv_delay": 1000},
    ),
    "pack_uv": (
        "~25004600F01001AF009C40B5400AFA24\r",
        "~250046D6F01001AF009C40B5400AFA0A\r",
        {"view_pack_uv_alarm": 44.8, "view_pack_uv_protect": 40.0, "view_pack_uv_release": 46.4, "view_pack_uv_delay": 1000},
    ),
    "charge_oc": (
        "~25004600400C010068006E0AFB1D\r",
        "~250046D8400C010068006E0AFB01\r",
        {"view_charge_current_alarm": 104, "view_charge_current_limit": 110, "view_charge_current_delay": 1000},
    ),
    "discharge_oc": (
        "~25004600400C01FF97FF920AFAD3\r",
        "~250046DA400C010069006E0AFAF7\r",
        {"view_discharge_current_alarm": 105, "view_discharge_current_limit": 110, "view_discharge_current_delay": 1000},
    ),
    "discharge_fast": (
        "~25004600400C009604009604FB32\r",
        "~250046E2A006009604FC4E\r",
        {"view_discharge_fast_current": 150, "view_discharge_fast_delay": 100},
    ),
    "short": (
        "~25004600E0020CFD25\r",
        "~250046E4E0020CFD0C\r",
        {"view_short_circuit_delay": 300},
    ),
    "balance": (
        "~2500460080080D48001EFBE9\r",
        "~250046B580080D48001EFBD2\r",
        {"view_balance_voltage": 3.4, "view_balance_delta": 30},
    ),
    "sleep": (
        "~2500460080080C1C0005FBF3\r",
        "~250046A880080C1C0005FBDA\r",
        {"view_sleep_voltage": 3.1, "view_sleep_delay": 5},
    ),
    "full": (
        "~25004600600ADAC007D005FB60\r",
        "~250046AE600ADAC007D005FB3A\r",
        {"view_full_charge_voltage": 56.0, "view_full_charge_current": 2.0, "view_low_soc_alarm": 5},
    ),
    "overtemp": (
        "~25004600501A010CA80CD00C9E0CDA0D020CD0F7BE\r",
        "~250046DC501A010CA80CD00C9E0CDA0D020CD0F797\r",
        {
            "view_charge_ot_alarm": 51,
            "view_charge_ot_protect": 55,
            "view_charge_ot_release": 50,
            "view_discharge_ot_alarm": 56,
            "view_discharge_ot_protect": 60,
            "view_discharge_ot_release": 55,
        },
    ),
    "undertemp": (
        "~25004600501A010AAA0A780AAA0A1409E20A14F7E5\r",
        "~250046DE501A010AAA0A780AAA0A1409E20A14F7BC\r",
        {
            "view_charge_ut_alarm": 0,
            "view_charge_ut_protect": -5,
            "view_charge_ut_release": 0,
            "view_discharge_ut_alarm": -15,
            "view_discharge_ut_protect": -20,
            "view_discharge_ut_release": -15,
        },
    ),
    "mosfet": (
        "~25004600200E010E2E0EF60DFCFA5D\r",
        "~250046E0200E010E2E0EF60DFCFA48\r",
        {"view_mosfet_ot_alarm": 90, "view_mosfet_ot_protect": 110, "view_mosfet_ot_release": 85},
    ),
    "environment": (
        "~25004600501A0109E209B009E20D340D660D34F806\r",
        "~250046E6501A0109E209B009E20D340D660D34F7EB\r",
        {
            "view_env_ut_alarm": -20,
            "view_env_ut_protect": -25,
            "view_env_ut_release": -20,
            "view_env_ot_alarm": 65,
            "view_env_ot_protect": 70,
            "view_env_ot_release": 65,
        },
    ),
    "limiter_start": (
        "~25004600C0040064FCCE\r",
        "~250046EEC0040064FCA4\r",
        {"view_limiter_start_current": 100},
    ),
    "capacity": (
        "~25004600400C183C286A2710FB0E\r",
        None,
        {
            "view_calibrated_remaining_capacity": 62.04,
            "view_calibrated_actual_capacity": 103.46,
            "view_calibrated_design_capacity": 100.0,
        },
    ),
    "clock": (
        "~25004600400C180815051D1FFB10\r",
        None,
        {"view_bms_clock": "2024-08-21 05:29:31"},
    ),
    "protocols": (
        "~25004600A006131400FC6F\r",
        None,
        {"view_can_protocol": "Afore", "view_rs485_protocol": "RONGKE", "view_protocol_mode": "Auto"},
    ),
}


def test_examples_decode_and_write_back_like_pbms_tools():
    bms = _bms()
    for group in GROUPS:
        read_frame, write_example, expected = EXAMPLES[group["name"]]
        payload = info_payload(read_frame)
        assert decode_group(group, payload) == expected
        if group["write"] is None:
            continue
        written = encode_group(group, payload, expected)
        frame = write_frame(bms, group, written)
        if group["name"] == "pack_ov":
            # The published write changes 57.60 V to 57.61 V. The roundtrip keeps 57.60 V.
            assert b"01E100E740D2F00A" in frame
            continue
        assert frame == write_example.encode("ascii")


def test_config_read_skips_a_pushed_frame():
    class Comm:
        def __init__(self):
            self.frames = [
                "~25004642E0020100F000\r",
                "~25004600400C180815051D1FFB10\r",
            ]

        def flush(self):
            return None

        def send_data(self, frame):
            return True

        def receive_data(self, timeout=None):
            return self.frames.pop(0) if self.frames else ""

    class Bms:
        def lchksum_calc(self, length):
            return "0"

        def chksum_calc(self, request):
            return "0000"

    bms = Bms()
    bms.bms_comm = Comm()
    group = next(item for item in GROUPS if item["name"] == "clock")
    assert read_group(bms, group) == bytes.fromhex("180815051D1F")
