"""Write Pace configuration frames. Values are always positive amps."""

import logging

_LOGGER = logging.getLogger(__name__)

# MOSFET close (01) connects the path. Open (00) disconnects it.
MOSFET_ON = "01"
MOSFET_OFF = "00"
LIMITER_ON = "0B"
LIMITER_OFF = "0A"
GEAR_HIGH = "08"
GEAR_LOW = "09"
# PBmsTools on the wire. The header enum has the buzzer bytes reversed.
BUZZER_ON = "0C"
BUZZER_OFF = "0D"
LED_ON = "07"
LED_OFF = "06"


def build_pace_request(bms, cid2, info, pack_number=None):
    """Build a PACE ASCII request. cid2 and info are hex text, for example 9A and 01."""
    address = _address(bms, pack_number)
    length = f"{len(info):03X}".encode("ascii")
    length_checksum = bms.lchksum_calc(length)
    if length_checksum is False:
        return None
    frame = (
        b"~25"
        + address
        + b"46"
        + cid2.encode("ascii")
        + length_checksum.encode("ascii")
        + length
        + info.encode("ascii")
    )
    checksum = bms.chksum_calc(frame)
    if checksum is False:
        return None
    return frame + checksum.encode("ascii") + b"\r"


def write_overcurrent(bms, kind, alarm_a, protection_a, delay_steps, pack_number=None):
    """Write D8H or DAH. Discharge is sent as a positive value, not as two's complement."""
    alarm_a = max(1, min(int(alarm_a), int(protection_a)))
    protection_a = max(1, int(protection_a))
    delay_steps = max(0, min(int(delay_steps), 255))
    payload = bytes(
        [
            0x01,
            (alarm_a >> 8) & 0xFF,
            alarm_a & 0xFF,
            (protection_a >> 8) & 0xFF,
            protection_a & 0xFF,
            delay_steps,
        ]
    )
    cid2 = "D8" if kind == "charge" else "DA"
    return _send(bms, cid2, payload.hex().upper(), pack_number)


def write_mosfet(bms, kind, enabled, pack_number=None):
    cid2 = "9A" if kind == "charge" else "9B"
    return _send(bms, cid2, MOSFET_ON if enabled else MOSFET_OFF, pack_number)


def write_limiter(bms, enabled, pack_number=None):
    return _send(bms, "99", LIMITER_ON if enabled else LIMITER_OFF, pack_number)


def write_limiter_gear(bms, gear, pack_number=None):
    info = GEAR_HIGH if gear == "high" else GEAR_LOW
    return _send(bms, "99", info, pack_number)


def write_buzzer(bms, enabled, pack_number=None):
    return _send(bms, "99", BUZZER_ON if enabled else BUZZER_OFF, pack_number)


def write_led(bms, enabled, pack_number=None):
    return _send(bms, "99", LED_ON if enabled else LED_OFF, pack_number)


def _address(bms, pack_number):
    if type(bms).__name__ == "PACEBMS485":
        number = 0 if pack_number is None else int(pack_number)
        return f"{number:02X}".encode("ascii")
    return b"00"


def _send(bms, cid2, info, pack_number):
    frame = build_pace_request(bms, cid2, info, pack_number)
    if not frame:
        return False
    try:
        bms.bms_comm.flush()
        if not bms.bms_comm.send_data(frame):
            return False
        response = bms.bms_comm.receive_data()
    except Exception as err:
        _LOGGER.warning("Pace write %s failed: %s", cid2, err)
        return False
    if not response:
        return False
    text = response.strip()
    if text.startswith("~"):
        text = text[1:]
    accepted = len(text) >= 8 and text[4:6] == "46" and text[6:8] == "00"
    if not accepted:
        _LOGGER.warning("Pace write %s was rejected: %s", cid2, response)
    return accepted
