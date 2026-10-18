"""Write Pace configuration frames. Values are always positive amps."""

import logging
from time import monotonic

_LOGGER = logging.getLogger(__name__)

# 9AH/9BH: 00 switches the MOSFET on, 01 switches it off (protocol doc; a PBmsTools
# capture shows 9A 01 clearing the CFET bit).
MOSFET_ON = "00"
MOSFET_OFF = "01"
# 99H: 0A switches the current limiter on, 0B off (protocol table A.43).
LIMITER_ON = "0A"
LIMITER_OFF = "0B"
GEAR_HIGH = "08"
GEAR_LOW = "09"
# 0D switches the buzzer alarm on, 0C off (protocol doc and PBmsTools capture).
BUZZER_ON = "0D"
BUZZER_OFF = "0C"
# 99H: 06 switches the LED alarm on, 07 off (protocol table A.43).
LED_ON = "06"
LED_OFF = "07"

# A write is confirmed by RTN 00 with an empty INFO (LENID 0). Only 9AH and 9BH answer
# with one status byte instead (LENID 2, protocol tables A.46 and A.48).
STATUS_BYTE_REPLIES = ("9A", "9B")
# A dongle forwards frames the BMS sends on its own; they keep CID2 42 (analog) or 44 (warning).
PUSHED_FRAMES = ("42", "44")
# Longest wait for the confirmation. Pushed analog frames that arrive meanwhile are skipped.
ACK_WAIT_SECONDS = 3.0


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


def write_clock(bms, moment, pack_number=None):
    """Write B2. The year is stored as year minus 2000."""
    if moment.year < 2000 or moment.year > 2255:
        return False
    payload = bytes(
        [
            moment.year - 2000,
            moment.month,
            moment.day,
            moment.hour,
            moment.minute,
            moment.second,
        ]
    )
    return _send(bms, "B2", payload.hex().upper(), pack_number)


def _address(bms, pack_number):
    if type(bms).__name__ == "PACEBMS485":
        number = 0 if pack_number is None else int(pack_number)
        return f"{number:02X}".encode("ascii")
    return b"00"


def reply_is_from_target(bms, reply_text, pack_number):
    """On RS485 every pack shares the bus, so the reply must carry the addressed pack.
    RS232 and the dongles link to one BMS only, and its reply address is not checked."""
    if type(bms).__name__ != "PACEBMS485":
        return True
    return reply_text[2:4] == _address(bms, pack_number).decode("ascii")


def ack_state(bms, cid2, reply, pack_number=None):
    """Classify one received frame: "ack", "rejected" (the target said no) or "other"."""
    text = (reply or "").strip()
    if text.startswith("~"):
        text = text[1:]
    if len(text) < 12 or text[4:6] != "46" or not reply_is_from_target(bms, text, pack_number):
        return "other"
    if text[6:8] in PUSHED_FRAMES:
        return "other"
    try:
        lenid = int(text[9:12], 16)
    except ValueError:
        return "other"
    allowed = (0, 2) if cid2 in STATUS_BYTE_REPLIES else (0,)
    if lenid not in allowed:
        return "other"
    return "ack" if text[6:8] == "00" else "rejected"


def await_ack(bms, cid2, pack_number=None):
    """Read replies until the write is confirmed, refused, or the wait is over."""
    deadline = monotonic() + ACK_WAIT_SECONDS
    while (remaining := deadline - monotonic()) > 0:
        reply = bms.bms_comm.receive_data(timeout=remaining)
        if not reply:
            _LOGGER.warning("Pace write %s got no reply", cid2)
            return False
        state = ack_state(bms, cid2, reply, pack_number)
        if state == "ack":
            return True
        if state == "rejected":
            _LOGGER.warning("Pace write %s was rejected: %s", cid2, reply)
            return False
    _LOGGER.warning("Pace write %s was not confirmed", cid2)
    return False


def _send(bms, cid2, info, pack_number):
    frame = build_pace_request(bms, cid2, info, pack_number)
    if not frame:
        return False
    try:
        bms.bms_comm.flush()
        if not bms.bms_comm.send_data(frame):
            return False
        return await_ack(bms, cid2, pack_number)
    except Exception as err:
        _LOGGER.warning("Pace write %s failed: %s", cid2, err)
        return False
