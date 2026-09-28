"""Read Pace charge and discharge current limits (commands D9H and DBH)."""

import logging

_LOGGER = logging.getLogger(__name__)

# Re-read configured limits once a minute. They do not change with every poll.
LIMIT_POLL_SECONDS = 60


def parse_pace_overcurrent_response(response):
    """Parse a D9H or DBH ASCII response into alarm and protection amps.

    Both frames store the same header: enable flag, alarm current (A),
    protection current (A). Discharge adds a recovery current before the delay.
    The protection threshold is the configured current limit. Alarm is used
    only when protection is zero.
    """
    if not response:
        return None
    text = response.strip()
    if text.startswith("~"):
        text = text[1:]
    if len(text) < 12:
        return None
    if text[4:6] != "46" or text[6:8] != "00":
        return None
    try:
        info_length = int(text[9:12], 16)
    except ValueError:
        return None
    info = text[12:12 + info_length]
    if len(info) < info_length or info_length < 10:
        return None
    try:
        payload = bytes.fromhex(info)
    except ValueError:
        return None
    if len(payload) < 5:
        return None
    alarm = int.from_bytes(payload[1:3], "big")
    protection = int.from_bytes(payload[3:5], "big")
    limit = protection if protection > 0 else alarm
    if limit <= 0:
        return None
    return {
        "enabled": payload[0] == 1,
        "alarm_a": alarm,
        "protection_a": protection,
        "limit_a": limit,
    }


def read_pace_current_limits(bms, pack_number=None):
    """Query CCL (D9H) and DCL (DBH). Returns None when the BMS does not answer."""
    charge = _read_overcurrent(bms, "charge_overcurrent", pack_number)
    discharge = _read_overcurrent(bms, "discharge_overcurrent", pack_number)
    if not charge and not discharge:
        return None
    limits = {}
    if charge:
        limits["view_charge_current_limit"] = charge["limit_a"]
    if discharge:
        limits["view_discharge_current_limit"] = discharge["limit_a"]
    return limits


def _read_overcurrent(bms, command, pack_number):
    try:
        request = bms.generate_bms_request(command, pack_number)
    except Exception as err:
        _LOGGER.debug("Cannot build %s request: %s", command, err)
        return None
    if not request:
        return None
    try:
        bms.bms_comm.flush()
        if not bms.bms_comm.send_data(request):
            return None
        response = bms.bms_comm.receive_data()
    except Exception as err:
        _LOGGER.debug("Current limit command %s failed: %s", command, err)
        return None
    parsed = parse_pace_overcurrent_response(response)
    if parsed is None:
        _LOGGER.debug("Current limit command %s returned no parseable frame: %s", command, response)
    return parsed
