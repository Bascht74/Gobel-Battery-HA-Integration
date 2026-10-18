"""A Pace write counts as done only when the addressed pack confirms it.

The confirmation is RTN 00 with an empty INFO (LENID 0). 9AH/9BH (MOSFET) answer
with one status byte instead. Frames the dongle pushes meanwhile, and on RS485 the
replies of other packs, are not the confirmation.
"""

from custom_components.gobel_battery.pace_config import GROUPS, read_group
from custom_components.gobel_battery.pace_write import build_pace_request, write_limiter_gear, write_mosfet
from custom_components.gobel_battery.pacebms_rs485 import PACEBMS485


class _Bus:
    """Hands out the queued replies one by one, then stays silent."""

    bms_connection = True

    def __init__(self, *replies):
        self.replies = list(replies)

    def flush(self):
        return None

    def send_data(self, _frame):
        return True

    def receive_data(self, timeout=None):
        return self.replies.pop(0) if self.replies else ""


def _rs485(*replies):
    return PACEBMS485(_Bus(*replies), object(), 5, 0, 0)


def reply(pack, rtn="00", info=""):
    """A reply frame: same layout as a request, with RTN where the command sits."""
    return build_pace_request(_rs485(), rtn, info, pack).decode("ascii")


def test_confirmation_from_the_addressed_pack_is_accepted():
    bms = _rs485(reply(pack=2))
    assert write_limiter_gear(bms, "high", pack_number=2) is True


def test_confirmation_from_another_pack_is_not_ours():
    # Pack 3 answers late to an earlier request; pack 2 stays silent.
    bms = _rs485(reply(pack=3))
    assert write_limiter_gear(bms, "high", pack_number=2) is False


def test_pushed_analog_frame_is_skipped_until_the_confirmation_comes():
    pushed_analog = reply(pack=2, rtn="42", info="00" * 40)
    bms = _rs485(pushed_analog, reply(pack=2))
    assert write_limiter_gear(bms, "high", pack_number=2) is True


def test_reply_with_data_is_not_a_confirmation():
    # RTN 00, but 8 data bytes: this answers a read, not the 99H write.
    bms = _rs485(reply(pack=2, info="010E100E740D340A"))
    assert write_limiter_gear(bms, "high", pack_number=2) is False


def test_refusal_of_the_pack_ends_the_wait():
    # RTN 06: invalid data
    bms = _rs485(reply(pack=2, rtn="06"), reply(pack=2))
    assert write_limiter_gear(bms, "high", pack_number=2) is False


def test_mosfet_confirmation_carries_the_status_byte():
    # 9AH answers with status 3 (here 0x02) in INFO, protocol table A.46
    bms = _rs485(reply(pack=2, info="02"))
    assert write_mosfet(bms, "charge", True, pack_number=2) is True


def test_settings_read_takes_the_reply_of_the_addressed_pack():
    # Before a write the group is read again. Pack 3's clock must not stand in for pack 2's.
    clock = next(group for group in GROUPS if group["name"] == "clock")
    bms = _rs485(reply(pack=3, info="180815051D1F"), reply(pack=2, info="18081505201F"))
    assert read_group(bms, clock, pack_number=2) == bytes.fromhex("18081505201F")
