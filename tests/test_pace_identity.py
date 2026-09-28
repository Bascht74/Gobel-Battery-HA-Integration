"""Identity frames use the Pace examples, not the mislabeled hardware name."""

from pace_config import info_payload
from pace_identity import parse_internal_version, parse_product_info, parse_software_version


def test_c1_example_is_the_firmware_string():
    payload = info_payload("~25014600602850313653313030412D313831322D312E30302000F58E\r")
    assert parse_software_version(payload) == {"software_version": "P16S100A-1812-1.00"}


def test_c2_example_is_the_bms_serial():
    payload = info_payload(
        "~25014600B05031383132313031333830333039442020202020202020202020202020202020202020202020202020EE0F\r"
    )
    assert parse_product_info(payload)["serial_number"] == "1812101380309D"


def test_c6_keeps_hardware_in_the_last_ten_bytes():
    payload = b"V4.00-014" + b" " * 11 + b"HW-PC200\x00\x00"
    assert parse_internal_version(payload) == {
        "internal_software_version": "V4.00-014",
        "hardware_version": "HW-PC200",
    }
