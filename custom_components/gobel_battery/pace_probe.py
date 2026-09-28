"""Tell a transparent TCP dongle apart from a passive Pace stream."""

import socket
import time

try:
    from .pacebms_rs232 import PACEBMS232
except ImportError:
    from pacebms_rs232 import PACEBMS232

ACTIVE = "active"
PASSIVE = "passive"
SILENT = "silent"


def pack_count_request():
    """A short Pace read. A transparent dongle forwards it; a passive stream ignores it."""
    driver = PACEBMS232(object(), object(), "PACE_LV", 5, 0, 0)
    return driver.generate_bms_request("pack_quantity")


def _frames(buffer):
    text = buffer.decode("ascii", errors="ignore")
    frames = []
    start = 0
    while True:
        mark = text.find("~", start)
        if mark < 0:
            break
        end = text.find("\r", mark)
        if end < 0:
            frames.append(text[mark:])
            break
        frames.append(text[mark:end])
        start = end + 1
    return frames, text


def classify_pace_traffic(before, after):
    """active = the BMS answered a command. passive = it only pushes frames."""
    _, after_text = _frames(after)
    for frame in _frames(after)[0]:
        if len(frame) >= 9 and frame[5:7] == "46" and frame[7:9] == "00":
            return ACTIVE
    for blob in (before, after):
        frames, text = _frames(blob)
        if "gobel" in text.lower():
            return PASSIVE
        for frame in frames:
            if len(frame) >= 9 and frame[5:7] == "46" and frame[7:9] in ("42", "44"):
                return PASSIVE
    if not before and not after:
        return SILENT
    return SILENT


def probe_pace_tcp(ip, port, timeout=4):
    """Connect, listen, send one read, and classify the answer."""
    sock = socket.create_connection((ip, int(port)), timeout=min(timeout, 5))
    try:
        before = _read_for(sock, 1.0)
        sock.sendall(pack_count_request())
        after = _read_for(sock, max(1.0, timeout - 1.0))
    finally:
        sock.close()
    return classify_pace_traffic(before, after)


def _read_for(sock, seconds):
    sock.settimeout(0.3)
    deadline = time.monotonic() + seconds
    data = b""
    while time.monotonic() < deadline:
        try:
            chunk = sock.recv(2048)
        except socket.timeout:
            continue
        if not chunk:
            break
        data += chunk
    return data
