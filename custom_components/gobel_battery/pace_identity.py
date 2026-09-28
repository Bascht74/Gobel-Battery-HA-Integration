"""Pace identity frames: firmware C1, serial C2, hardware C6."""

try:
    from .pace_config import info_payload
    from .pace_write import build_pace_request
except ImportError:
    from pace_config import info_payload
    from pace_write import build_pace_request


def _text(payload, start, length):
    chunk = payload[start:start + length]
    return chunk.split(b"\x00", 1)[0].decode("ascii", errors="ignore").strip()


def parse_software_version(payload):
    """C1. Twenty characters of firmware, optional Bluetooth name after that."""
    if not payload:
        return {}
    software = _text(payload, 0, 20)
    return {"software_version": software} if software else {}


def parse_product_info(payload):
    """C2. BMS serial, then an optional pack serial."""
    if not payload:
        return {}
    serial = _text(payload, 0, 20)
    found = {"serial_number": serial} if serial else {}
    if len(payload) >= 40:
        pack_serial = _text(payload, 20, 20)
        if pack_serial:
            found["pack_serial"] = pack_serial
    return found


def parse_internal_version(payload):
    """C6. Software text, with the hardware version in the last ten bytes."""
    if not payload or len(payload) < 10:
        return {}
    hardware = _text(payload, len(payload) - 10, 10)
    software = _text(payload, 0, max(0, len(payload) - 10))
    found = {}
    if hardware:
        found["hardware_version"] = hardware
    if software:
        found["internal_software_version"] = software
    return found


def read_identity(bms, pack_number=None):
    """Read the three identity commands. Missing answers are skipped."""
    found = {}
    for cid, parser in (
        ("C1", parse_software_version),
        ("C2", parse_product_info),
        ("C6", parse_internal_version),
    ):
        frame = build_pace_request(bms, cid, "", pack_number)
        if not frame:
            continue
        try:
            bms.bms_comm.flush()
            if not bms.bms_comm.send_data(frame):
                continue
            response = bms.bms_comm.receive_data()
        except Exception:
            continue
        if not response:
            continue
        parsed = parser(info_payload(response))
        found.update(parsed)
    if not found.get("software_version"):
        internal = found.get("internal_software_version")
        if internal:
            found["software_version"] = internal
    return found
