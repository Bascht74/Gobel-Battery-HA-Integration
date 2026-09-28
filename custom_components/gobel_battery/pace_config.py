"""Pace protection and system settings from the PBmsTools pages.

Each group is one read/write command. A write sends the whole group back,
so the raw payload is kept and only the edited field changes.
Discharge overcurrent is read as a negative word and written as a positive one.
"""

import logging

try:
    from .pace_write import build_pace_request
except ImportError:
    from pace_write import build_pace_request

_LOGGER = logging.getLogger(__name__)

GROUPS_PER_POLL = 4


def _mv(payload, offset):
    return int.from_bytes(payload[offset:offset + 2], "big") / 1000.0


def _put_mv(payload, offset, volts):
    payload[offset:offset + 2] = int(round(float(volts) * 1000)).to_bytes(2, "big")


def _amps(payload, offset, signed=False):
    word = int.from_bytes(payload[offset:offset + 2], "big")
    if signed and word >= 0x8000:
        word -= 0x10000
    return abs(word)


def _put_amps(payload, offset, amps):
    payload[offset:offset + 2] = int(round(abs(float(amps)))).to_bytes(2, "big")


def _celsius(payload, offset):
    return round((int.from_bytes(payload[offset:offset + 2], "big") - 2730) / 10.0, 1)


def _put_celsius(payload, offset, degrees):
    raw = int(round(float(degrees) * 10 + 2730))
    payload[offset:offset + 2] = raw.to_bytes(2, "big")


def _delay_ms(payload, offset, step):
    return payload[offset] * step


def _put_delay(payload, offset, display, step):
    payload[offset] = int(round(float(display) / step))


FIELDS = (
    {"key": "cell_ov_alarm", "name": "Cell Overvoltage Alarm", "group": "cell_ov", "unit": "V", "min": 2.5, "max": 4.5, "step": 0.01, "precision": 2, "device_class": "voltage", "icon": "mdi:battery-alert"},
    {"key": "cell_ov_protect", "name": "Cell Overvoltage Protection", "group": "cell_ov", "unit": "V", "min": 2.5, "max": 4.5, "step": 0.01, "precision": 2, "device_class": "voltage", "icon": "mdi:battery-alert"},
    {"key": "cell_ov_release", "name": "Cell Overvoltage Release", "group": "cell_ov", "unit": "V", "min": 2.5, "max": 4.5, "step": 0.01, "precision": 2, "device_class": "voltage", "icon": "mdi:battery-alert"},
    {"key": "cell_ov_delay", "name": "Cell Overvoltage Delay", "group": "cell_ov", "unit": "ms", "min": 1000, "max": 20000, "step": 500, "precision": 0, "device_class": None, "icon": "mdi:timer"},
    {"key": "pack_ov_alarm", "name": "Pack Overvoltage Alarm", "group": "pack_ov", "unit": "V", "min": 20, "max": 65, "step": 0.01, "precision": 2, "device_class": "voltage", "icon": "mdi:battery-alert"},
    {"key": "pack_ov_protect", "name": "Pack Overvoltage Protection", "group": "pack_ov", "unit": "V", "min": 20, "max": 65, "step": 0.01, "precision": 2, "device_class": "voltage", "icon": "mdi:battery-alert"},
    {"key": "pack_ov_release", "name": "Pack Overvoltage Release", "group": "pack_ov", "unit": "V", "min": 20, "max": 65, "step": 0.01, "precision": 2, "device_class": "voltage", "icon": "mdi:battery-alert"},
    {"key": "pack_ov_delay", "name": "Pack Overvoltage Delay", "group": "pack_ov", "unit": "ms", "min": 1000, "max": 20000, "step": 500, "precision": 0, "device_class": None, "icon": "mdi:timer"},
    {"key": "cell_uv_alarm", "name": "Cell Undervoltage Alarm", "group": "cell_uv", "unit": "V", "min": 2.0, "max": 3.5, "step": 0.01, "precision": 2, "device_class": "voltage", "icon": "mdi:battery-alert"},
    {"key": "cell_uv_protect", "name": "Cell Undervoltage Protection", "group": "cell_uv", "unit": "V", "min": 2.0, "max": 3.5, "step": 0.01, "precision": 2, "device_class": "voltage", "icon": "mdi:battery-alert"},
    {"key": "cell_uv_release", "name": "Cell Undervoltage Release", "group": "cell_uv", "unit": "V", "min": 2.0, "max": 3.5, "step": 0.01, "precision": 2, "device_class": "voltage", "icon": "mdi:battery-alert"},
    {"key": "cell_uv_delay", "name": "Cell Undervoltage Delay", "group": "cell_uv", "unit": "ms", "min": 1000, "max": 20000, "step": 500, "precision": 0, "device_class": None, "icon": "mdi:timer"},
    {"key": "pack_uv_alarm", "name": "Pack Undervoltage Alarm", "group": "pack_uv", "unit": "V", "min": 15, "max": 50, "step": 0.01, "precision": 2, "device_class": "voltage", "icon": "mdi:battery-alert"},
    {"key": "pack_uv_protect", "name": "Pack Undervoltage Protection", "group": "pack_uv", "unit": "V", "min": 15, "max": 50, "step": 0.01, "precision": 2, "device_class": "voltage", "icon": "mdi:battery-alert"},
    {"key": "pack_uv_release", "name": "Pack Undervoltage Release", "group": "pack_uv", "unit": "V", "min": 15, "max": 50, "step": 0.01, "precision": 2, "device_class": "voltage", "icon": "mdi:battery-alert"},
    {"key": "pack_uv_delay", "name": "Pack Undervoltage Delay", "group": "pack_uv", "unit": "ms", "min": 1000, "max": 20000, "step": 500, "precision": 0, "device_class": None, "icon": "mdi:timer"},
    {"key": "charge_current_alarm", "name": "Charge Current Alarm", "group": "charge_oc", "unit": "A", "min": 1, "max": 220, "step": 1, "precision": 0, "device_class": "current", "icon": "mdi:current-dc"},
    {"key": "charge_current_limit", "name": "Charge Current Limit", "group": "charge_oc", "unit": "A", "min": 1, "max": 220, "step": 1, "precision": 0, "device_class": "current", "icon": "mdi:current-dc"},
    {"key": "charge_current_delay", "name": "Charge Current Delay", "group": "charge_oc", "unit": "ms", "min": 500, "max": 25000, "step": 500, "precision": 0, "device_class": None, "icon": "mdi:timer"},
    {"key": "discharge_current_alarm", "name": "Discharge Current Alarm", "group": "discharge_oc", "unit": "A", "min": 1, "max": 220, "step": 1, "precision": 0, "device_class": "current", "icon": "mdi:current-dc"},
    {"key": "discharge_current_limit", "name": "Discharge Current Limit", "group": "discharge_oc", "unit": "A", "min": 1, "max": 220, "step": 1, "precision": 0, "device_class": "current", "icon": "mdi:current-dc"},
    {"key": "discharge_current_delay", "name": "Discharge Current Delay", "group": "discharge_oc", "unit": "ms", "min": 500, "max": 25000, "step": 500, "precision": 0, "device_class": None, "icon": "mdi:timer"},
    {"key": "discharge_fast_current", "name": "Discharge Fast Current Limit", "group": "discharge_fast", "unit": "A", "min": 5, "max": 255, "step": 5, "precision": 0, "device_class": "current", "icon": "mdi:current-dc"},
    {"key": "discharge_fast_delay", "name": "Discharge Fast Current Delay", "group": "discharge_fast", "unit": "ms", "min": 100, "max": 2000, "step": 100, "precision": 0, "device_class": None, "icon": "mdi:timer"},
    {"key": "short_circuit_delay", "name": "Short Circuit Delay", "group": "short", "unit": "µs", "min": 100, "max": 500, "step": 50, "precision": 0, "device_class": None, "icon": "mdi:flash"},
    {"key": "balance_voltage", "name": "Balance Voltage", "group": "balance", "unit": "V", "min": 3.3, "max": 4.5, "step": 0.01, "precision": 2, "device_class": "voltage", "icon": "mdi:scale-balance"},
    {"key": "balance_delta", "name": "Balance Delta", "group": "balance", "unit": "mV", "min": 20, "max": 500, "step": 5, "precision": 0, "device_class": None, "icon": "mdi:scale-balance"},
    {"key": "sleep_voltage", "name": "Sleep Cell Voltage", "group": "sleep", "unit": "V", "min": 2.0, "max": 4.0, "step": 0.01, "precision": 2, "device_class": "voltage", "icon": "mdi:sleep"},
    {"key": "sleep_delay", "name": "Sleep Delay", "group": "sleep", "unit": "min", "min": 1, "max": 120, "step": 1, "precision": 0, "device_class": None, "icon": "mdi:timer"},
    {"key": "full_charge_voltage", "name": "Full Charge Voltage", "group": "full", "unit": "V", "min": 20, "max": 65, "step": 0.01, "precision": 2, "device_class": "voltage", "icon": "mdi:battery-charging"},
    {"key": "full_charge_current", "name": "Full Charge Current", "group": "full", "unit": "A", "min": 0.5, "max": 5.0, "step": 0.5, "precision": 1, "device_class": "current", "icon": "mdi:current-dc"},
    {"key": "low_soc_alarm", "name": "Low SOC Alarm", "group": "full", "unit": "%", "min": 0, "max": 100, "step": 1, "precision": 0, "device_class": None, "icon": "mdi:battery-low"},
    {"key": "charge_ot_alarm", "name": "Charge Overtemperature Alarm", "group": "overtemp", "unit": "°C", "min": 20, "max": 100, "step": 1, "precision": 0, "device_class": "temperature", "icon": "mdi:thermometer-alert"},
    {"key": "charge_ot_protect", "name": "Charge Overtemperature Protection", "group": "overtemp", "unit": "°C", "min": 20, "max": 100, "step": 1, "precision": 0, "device_class": "temperature", "icon": "mdi:thermometer-alert"},
    {"key": "charge_ot_release", "name": "Charge Overtemperature Release", "group": "overtemp", "unit": "°C", "min": 20, "max": 100, "step": 1, "precision": 0, "device_class": "temperature", "icon": "mdi:thermometer"},
    {"key": "discharge_ot_alarm", "name": "Discharge Overtemperature Alarm", "group": "overtemp", "unit": "°C", "min": 20, "max": 100, "step": 1, "precision": 0, "device_class": "temperature", "icon": "mdi:thermometer-alert"},
    {"key": "discharge_ot_protect", "name": "Discharge Overtemperature Protection", "group": "overtemp", "unit": "°C", "min": 20, "max": 100, "step": 1, "precision": 0, "device_class": "temperature", "icon": "mdi:thermometer-alert"},
    {"key": "discharge_ot_release", "name": "Discharge Overtemperature Release", "group": "overtemp", "unit": "°C", "min": 20, "max": 100, "step": 1, "precision": 0, "device_class": "temperature", "icon": "mdi:thermometer"},
    {"key": "charge_ut_alarm", "name": "Charge Undertemperature Alarm", "group": "undertemp", "unit": "°C", "min": -35, "max": 30, "step": 1, "precision": 0, "device_class": "temperature", "icon": "mdi:thermometer-alert"},
    {"key": "charge_ut_protect", "name": "Charge Undertemperature Protection", "group": "undertemp", "unit": "°C", "min": -35, "max": 30, "step": 1, "precision": 0, "device_class": "temperature", "icon": "mdi:thermometer-alert"},
    {"key": "charge_ut_release", "name": "Charge Undertemperature Release", "group": "undertemp", "unit": "°C", "min": -35, "max": 30, "step": 1, "precision": 0, "device_class": "temperature", "icon": "mdi:thermometer"},
    {"key": "discharge_ut_alarm", "name": "Discharge Undertemperature Alarm", "group": "undertemp", "unit": "°C", "min": -35, "max": 30, "step": 1, "precision": 0, "device_class": "temperature", "icon": "mdi:thermometer-alert"},
    {"key": "discharge_ut_protect", "name": "Discharge Undertemperature Protection", "group": "undertemp", "unit": "°C", "min": -35, "max": 30, "step": 1, "precision": 0, "device_class": "temperature", "icon": "mdi:thermometer-alert"},
    {"key": "discharge_ut_release", "name": "Discharge Undertemperature Release", "group": "undertemp", "unit": "°C", "min": -35, "max": 30, "step": 1, "precision": 0, "device_class": "temperature", "icon": "mdi:thermometer"},
    {"key": "mosfet_ot_alarm", "name": "MOSFET Overtemperature Alarm", "group": "mosfet", "unit": "°C", "min": 30, "max": 120, "step": 1, "precision": 0, "device_class": "temperature", "icon": "mdi:thermometer-alert"},
    {"key": "mosfet_ot_protect", "name": "MOSFET Overtemperature Protection", "group": "mosfet", "unit": "°C", "min": 30, "max": 120, "step": 1, "precision": 0, "device_class": "temperature", "icon": "mdi:thermometer-alert"},
    {"key": "mosfet_ot_release", "name": "MOSFET Overtemperature Release", "group": "mosfet", "unit": "°C", "min": 30, "max": 120, "step": 1, "precision": 0, "device_class": "temperature", "icon": "mdi:thermometer"},
    {"key": "env_ut_alarm", "name": "Environment Undertemperature Alarm", "group": "environment", "unit": "°C", "min": -35, "max": 30, "step": 1, "precision": 0, "device_class": "temperature", "icon": "mdi:thermometer-alert"},
    {"key": "env_ut_protect", "name": "Environment Undertemperature Protection", "group": "environment", "unit": "°C", "min": -35, "max": 30, "step": 1, "precision": 0, "device_class": "temperature", "icon": "mdi:thermometer-alert"},
    {"key": "env_ut_release", "name": "Environment Undertemperature Release", "group": "environment", "unit": "°C", "min": -35, "max": 30, "step": 1, "precision": 0, "device_class": "temperature", "icon": "mdi:thermometer"},
    {"key": "env_ot_alarm", "name": "Environment Overtemperature Alarm", "group": "environment", "unit": "°C", "min": 20, "max": 100, "step": 1, "precision": 0, "device_class": "temperature", "icon": "mdi:thermometer-alert"},
    {"key": "env_ot_protect", "name": "Environment Overtemperature Protection", "group": "environment", "unit": "°C", "min": 20, "max": 100, "step": 1, "precision": 0, "device_class": "temperature", "icon": "mdi:thermometer-alert"},
    {"key": "env_ot_release", "name": "Environment Overtemperature Release", "group": "environment", "unit": "°C", "min": 20, "max": 100, "step": 1, "precision": 0, "device_class": "temperature", "icon": "mdi:thermometer"},
    {"key": "limiter_start_current", "name": "Charge Limiter Start Current", "group": "limiter_start", "unit": "A", "min": 5, "max": 150, "step": 1, "precision": 0, "device_class": "current", "icon": "mdi:current-dc"},
)

READ_ONLY = (
    {"key": "calibrated_remaining_capacity", "name": "Calibrated Remaining Capacity", "unit": "Ah", "device_class": None, "icon": "mdi:battery-heart", "precision": 2},
    {"key": "calibrated_actual_capacity", "name": "Calibrated Actual Capacity", "unit": "Ah", "device_class": None, "icon": "mdi:battery-heart", "precision": 2},
    {"key": "calibrated_design_capacity", "name": "Calibrated Design Capacity", "unit": "Ah", "device_class": None, "icon": "mdi:battery-heart", "precision": 2},
    {"key": "bms_clock", "name": "BMS Clock", "unit": None, "device_class": None, "icon": "mdi:clock-outline", "precision": None},
    {"key": "can_protocol", "name": "CAN Protocol", "unit": None, "device_class": None, "icon": "mdi:lan", "precision": None},
    {"key": "rs485_protocol", "name": "RS485 Protocol", "unit": None, "device_class": None, "icon": "mdi:lan", "precision": None},
    {"key": "protocol_mode", "name": "Protocol Mode", "unit": None, "device_class": None, "icon": "mdi:lan", "precision": None},
)

FIELD_BY_KEY = {field["key"]: field for field in FIELDS}

# decode(payload) -> values, encode(payload, values) mutates a bytearray.
def _voltage_group(keys):
    def decode(payload):
        return {
            keys[0]: round(_mv(payload, 1), 2),
            keys[1]: round(_mv(payload, 3), 2),
            keys[2]: round(_mv(payload, 5), 2),
            keys[3]: _delay_ms(payload, 7, 100),
        }

    def encode(payload, values):
        _put_mv(payload, 1, values[keys[0]])
        _put_mv(payload, 3, values[keys[1]])
        _put_mv(payload, 5, values[keys[2]])
        _put_delay(payload, 7, values[keys[3]], 100)

    return decode, encode


def _current_group(keys, signed):
    def decode(payload):
        return {
            keys[0]: _amps(payload, 1, signed),
            keys[1]: _amps(payload, 3, signed),
            keys[2]: _delay_ms(payload, 5, 100),
        }

    def encode(payload, values):
        _put_amps(payload, 1, values[keys[0]])
        _put_amps(payload, 3, values[keys[1]])
        _put_delay(payload, 5, values[keys[2]], 100)

    return decode, encode


def _decode_fast(payload):
    return {
        "discharge_fast_current": payload[1],
        "discharge_fast_delay": payload[2] * 25,
    }


def _encode_fast(payload, values):
    payload[0] = 0
    payload[1] = int(round(values["discharge_fast_current"]))
    payload[2] = int(round(values["discharge_fast_delay"] / 25))


def _decode_short(payload):
    return {"short_circuit_delay": payload[0] * 25}


def _encode_short(payload, values):
    payload[0] = int(round(values["short_circuit_delay"] / 25))


def _decode_balance(payload):
    return {"balance_voltage": round(_mv(payload, 0), 2), "balance_delta": _mv(payload, 2) * 1000}


def _encode_balance(payload, values):
    _put_mv(payload, 0, values["balance_voltage"])
    payload[2:4] = int(round(values["balance_delta"])).to_bytes(2, "big")


def _decode_sleep(payload):
    return {"sleep_voltage": round(_mv(payload, 0), 2), "sleep_delay": payload[3]}


def _encode_sleep(payload, values):
    _put_mv(payload, 0, values["sleep_voltage"])
    payload[3] = int(round(values["sleep_delay"]))


def _decode_full(payload):
    return {
        "full_charge_voltage": round(_mv(payload, 0), 2),
        "full_charge_current": round(_mv(payload, 2), 1),
        "low_soc_alarm": payload[4],
    }


def _encode_full(payload, values):
    _put_mv(payload, 0, values["full_charge_voltage"])
    payload[2:4] = int(round(values["full_charge_current"] * 1000)).to_bytes(2, "big")
    payload[4] = int(round(values["low_soc_alarm"]))


def _temp_group(keys, start):
    def decode(payload):
        return {key: _celsius(payload, start + index * 2) for index, key in enumerate(keys)}

    def encode(payload, values):
        for index, key in enumerate(keys):
            _put_celsius(payload, start + index * 2, values[key])

    return decode, encode


def _decode_limiter(payload):
    return {"limiter_start_current": int.from_bytes(payload[0:2], "big")}


def _encode_limiter(payload, values):
    payload[0:2] = int(round(values["limiter_start_current"])).to_bytes(2, "big")


def _ah(payload, offset):
    return round(int.from_bytes(payload[offset:offset + 2], "big") / 100.0, 2)


def _decode_capacity(payload):
    return {
        "calibrated_remaining_capacity": _ah(payload, 0),
        "calibrated_actual_capacity": _ah(payload, 2),
        "calibrated_design_capacity": _ah(payload, 4),
    }


def _decode_clock(payload):
    year = 2000 + payload[0]
    stamp = f"{year:04d}-{payload[1]:02d}-{payload[2]:02d} {payload[3]:02d}:{payload[4]:02d}:{payload[5]:02d}"
    return {"bms_clock": stamp}


CAN_PROTOCOLS = {
    0xFF: "Off",
    0x00: "PACE",
    0x01: "Pylon",
    0x02: "Growatt",
    0x03: "Victron",
    0x04: "Schneider",
    0x05: "LuxPower",
    0x06: "SoroTec",
    0x07: "SMA",
    0x08: "GoodWe",
    0x09: "Studer",
    0x0A: "Sofar",
    0x0B: "Must",
    0x0C: "Solis",
    0x0D: "DIDU",
    0x0E: "Senergy",
    0x0F: "TBB",
    0x10: "Pylon V202",
    0x11: "Growatt V109",
    0x12: "Must V202",
    0x13: "Afore",
    0x14: "INVT",
    0x15: "FUJI",
    0x16: "Sofar V21003",
}

RS485_PROTOCOLS = {
    0xFF: "Off",
    0x00: "Pace Modbus",
    0x01: "Pylon",
    0x02: "Growatt",
    0x03: "Voltronic",
    0x04: "Schneider",
    0x05: "PHOCOS",
    0x06: "LuxPower",
    0x07: "Solar",
    0x08: "Lithium",
    0x09: "EP",
    0x0A: "RTU04",
    0x0B: "LuxPower V01",
    0x0C: "LuxPower V03",
    0x0D: "SRNE",
    0x0E: "LEOCH",
    0x0F: "Pylon F",
    0x10: "Afore",
    0x11: "UPS AGXN",
    0x12: "Orex Sunpolo",
    0x13: "XIONGTAO",
    0x14: "RONGKE",
    0x15: "XINRUI",
    0x16: "ELTEK",
    0x17: "GT",
    0x18: "Leoch V106",
}


def _protocol_name(table, code):
    return table.get(code, f"Unknown {code}")


def _decode_protocols(payload):
    return {
        "can_protocol": _protocol_name(CAN_PROTOCOLS, payload[0]),
        "rs485_protocol": _protocol_name(RS485_PROTOCOLS, payload[1]),
        "protocol_mode": {0x00: "Auto", 0x01: "Manual", 0xFF: "Off"}.get(payload[2], f"Unknown {payload[2]}"),
    }


def _keep(payload, values):
    return None


_OVER = (
    "charge_ot_alarm",
    "charge_ot_protect",
    "charge_ot_release",
    "discharge_ot_alarm",
    "discharge_ot_protect",
    "discharge_ot_release",
)
_UNDER = (
    "charge_ut_alarm",
    "charge_ut_protect",
    "charge_ut_release",
    "discharge_ut_alarm",
    "discharge_ut_protect",
    "discharge_ut_release",
)
_ENV = (
    "env_ut_alarm",
    "env_ut_protect",
    "env_ut_release",
    "env_ot_alarm",
    "env_ot_protect",
    "env_ot_release",
)

GROUPS = (
    {"name": "cell_ov", "read": "D1", "write": "D0", "write_length": 8, **dict(zip(("decode", "encode"), _voltage_group(("cell_ov_alarm", "cell_ov_protect", "cell_ov_release", "cell_ov_delay"))))},
    {"name": "pack_ov", "read": "D5", "write": "D4", "write_length": 8, **dict(zip(("decode", "encode"), _voltage_group(("pack_ov_alarm", "pack_ov_protect", "pack_ov_release", "pack_ov_delay"))))},
    {"name": "cell_uv", "read": "D3", "write": "D2", "write_length": 8, **dict(zip(("decode", "encode"), _voltage_group(("cell_uv_alarm", "cell_uv_protect", "cell_uv_release", "cell_uv_delay"))))},
    {"name": "pack_uv", "read": "D7", "write": "D6", "write_length": 8, **dict(zip(("decode", "encode"), _voltage_group(("pack_uv_alarm", "pack_uv_protect", "pack_uv_release", "pack_uv_delay"))))},
    {"name": "charge_oc", "read": "D9", "write": "D8", "write_length": 6, **dict(zip(("decode", "encode"), _current_group(("charge_current_alarm", "charge_current_limit", "charge_current_delay"), False)))},
    {"name": "discharge_oc", "read": "DB", "write": "DA", "write_length": 6, **dict(zip(("decode", "encode"), _current_group(("discharge_current_alarm", "discharge_current_limit", "discharge_current_delay"), True)))},
    {"name": "discharge_fast", "read": "E3", "write": "E2", "write_length": 3, "decode": _decode_fast, "encode": _encode_fast},
    {"name": "short", "read": "E5", "write": "E4", "write_length": 1, "decode": _decode_short, "encode": _encode_short},
    {"name": "balance", "read": "B6", "write": "B5", "write_length": 4, "decode": _decode_balance, "encode": _encode_balance},
    {"name": "sleep", "read": "A0", "write": "A8", "write_length": 4, "decode": _decode_sleep, "encode": _encode_sleep},
    {"name": "full", "read": "AF", "write": "AE", "write_length": 5, "decode": _decode_full, "encode": _encode_full},
    {"name": "overtemp", "read": "DD", "write": "DC", "write_length": 13, **dict(zip(("decode", "encode"), _temp_group(_OVER, 1)))},
    {"name": "undertemp", "read": "DF", "write": "DE", "write_length": 13, **dict(zip(("decode", "encode"), _temp_group(_UNDER, 1)))},
    {"name": "mosfet", "read": "E1", "write": "E0", "write_length": 7, **dict(zip(("decode", "encode"), _temp_group(("mosfet_ot_alarm", "mosfet_ot_protect", "mosfet_ot_release"), 1)))},
    {"name": "environment", "read": "E7", "write": "E6", "write_length": 13, **dict(zip(("decode", "encode"), _temp_group(_ENV, 1)))},
    {"name": "limiter_start", "read": "ED", "write": "EE", "write_length": 2, "decode": _decode_limiter, "encode": _encode_limiter},
    {"name": "capacity", "read": "A6", "write": None, "write_length": 6, "decode": _decode_capacity, "encode": _keep},
    {"name": "clock", "read": "B1", "write": None, "write_length": 6, "decode": _decode_clock, "encode": _keep},
    {"name": "protocols", "read": "EB", "write": None, "write_length": 3, "decode": _decode_protocols, "encode": _keep},
)

GROUP_BY_NAME = {group["name"]: group for group in GROUPS}


def info_payload(frame):
    """Return the INFO bytes of a Pace ASCII frame."""
    text = frame.strip()
    if text.startswith("~"):
        text = text[1:]
    if len(text) < 16 or text[4:6] != "46" or text[6:8] != "00":
        return None
    try:
        length = int(text[9:12], 16)
    except ValueError:
        return None
    info = text[12:12 + length]
    if len(info) < length:
        return None
    try:
        return bytes.fromhex(info)
    except ValueError:
        return None


def decode_group(group, payload):
    if payload is None:
        return {}
    try:
        values = group["decode"](payload)
    except (IndexError, ValueError):
        return {}
    return {f"view_{key}": value for key, value in values.items()}


def encode_group(group, payload, values):
    """Return the write payload after replacing fields present in values."""
    updated = bytearray(payload)
    plain = {key.removeprefix("view_"): value for key, value in values.items()}
    group["encode"](updated, plain)
    return bytes(updated[: group["write_length"]])


def write_frame(bms, group, payload, pack_number=None):
    info = payload.hex().upper()
    return build_pace_request(bms, group["write"], info, pack_number)


def read_group(bms, group, pack_number=None):
    frame = build_pace_request(bms, group["read"], "", pack_number)
    if not frame:
        return None
    try:
        bms.bms_comm.flush()
        if not bms.bms_comm.send_data(frame):
            return None
        return info_payload(bms.bms_comm.receive_data())
    except Exception as err:
        _LOGGER.debug("Pace config %s failed: %s", group["read"], err)
        return None


def read_configuration_slice(bms, start, count=GROUPS_PER_POLL, pack_number=None):
    """Read the next few configuration groups. Returns values and raw payloads."""
    values = {}
    raw = {}
    total = len(GROUPS)
    for offset in range(count):
        group = GROUPS[(start + offset) % total]
        payload = read_group(bms, group, pack_number)
        if not payload:
            continue
        raw[group["name"]] = payload
        values.update(decode_group(group, payload))
    return values, raw


def write_configuration_field(bms, key, value, raw_payload, pack_number=None):
    """Write one field and return the new raw payload, or None on failure."""
    field = FIELD_BY_KEY[key]
    group = GROUP_BY_NAME[field["group"]]
    merged = decode_group(group, raw_payload)
    merged[f"view_{key}"] = value
    payload = encode_group(group, raw_payload, merged)
    frame = write_frame(bms, group, payload, pack_number)
    if not frame:
        return None
    try:
        bms.bms_comm.flush()
        if not bms.bms_comm.send_data(frame):
            return None
        response = bms.bms_comm.receive_data()
    except Exception as err:
        _LOGGER.warning("Pace config write %s failed: %s", key, err)
        return None
    text = (response or "").strip()
    if text.startswith("~"):
        text = text[1:]
    if len(text) < 8 or text[4:6] != "46" or text[6:8] != "00":
        return None
    return payload
