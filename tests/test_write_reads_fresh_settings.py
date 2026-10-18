"""A settings write sends the whole group back, so it reads the group from the BMS first.

Scenario: the coordinator read Cell Overvoltage a few minutes ago (alarm 3.60 V).
Since then the alarm was changed to 3.55 V in PBmsTools. Now the user sets the
protection to 3.65 V in Home Assistant. The write must keep 3.55 V, not the old 3.60 V.
"""

from custom_components.gobel_battery.pace_write import build_pace_request
from custom_components.gobel_battery.pacebms_rs232 import PACEBMS232
from fake_hass import make_coordinator

# Cell overvoltage group: 01, alarm, protection, release in mV, delay
OLD_GROUP = "01" + "0E10" + "0E74" + "0D34" + "0A"  # 3.60 V, 3.70 V, 3.38 V
NOW_IN_BMS = "01" + "0DDE" + "0E74" + "0D34" + "0A"  # alarm changed to 3.55 V
WRITTEN = "01" + "0DDE" + "0E42" + "0D34" + "0A"  # protection 3.65 V, alarm stays 3.55 V


class _Bms232:
    """Answers D1 (read cell overvoltage) with NOW_IN_BMS and confirms D0 (write)."""

    bms_connection = True

    def __init__(self):
        self.sent = []
        self.pending = ""
        self.bms = PACEBMS232(self, object(), "PACE_LV", 5, 0, 0)

    def flush(self):
        return None

    def send_data(self, frame):
        self.sent.append(frame.decode("ascii"))
        command = frame[7:9].decode("ascii")
        info = NOW_IN_BMS if command == "D1" else ""
        self.pending = build_pace_request(self.bms, "00", info).decode("ascii")
        return True

    def receive_data(self, timeout=None):
        answer, self.pending = self.pending, ""
        return answer


def test_write_keeps_a_value_changed_meanwhile_in_pbms_tools():
    link = _Bms232()
    coordinator = make_coordinator()
    coordinator.bms = link.bms
    coordinator._config_cache["all"] = {
        "cursor": 0,
        "values": {},
        "raw": {"cell_ov": bytes.fromhex(OLD_GROUP)},
        "ts": 0,
    }

    assert coordinator._apply_expert_change_sync(0, "cell_ov_protect", 3.65) is True

    write = next(frame for frame in link.sent if frame[7:9] == "D0")
    # ~ 25 00 46 D0 LLLL <INFO> CCCC \r
    assert write[13:-5] == WRITTEN
