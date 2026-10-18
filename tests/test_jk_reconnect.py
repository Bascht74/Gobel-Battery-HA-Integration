"""Only one place may reconnect a JK link, and a reconnect never leaves the old socket open.

The JK listener thread reconnects after 15 s without data. If the poll reconnected
as well, two threads would swap the socket under each other, and dongles that
accept only one client would refuse the second session.
"""

import socket as real_socket
import types

from custom_components.gobel_battery import bms_comm
from custom_components.gobel_battery.bms_comm import BMSCommunication
from fake_hass import make_coordinator


class _Socket:
    def __init__(self):
        self.closed = False

    def settimeout(self, _seconds):
        return None

    def setsockopt(self, *_args):
        return None

    def connect(self, _address):
        return None

    def close(self):
        self.closed = True


def test_a_new_connect_closes_the_old_socket(monkeypatch):
    opened = []

    def new_socket(*_args):
        opened.append(_Socket())
        return opened[-1]

    fake = types.SimpleNamespace(
        socket=new_socket,
        AF_INET=real_socket.AF_INET,
        SOCK_STREAM=real_socket.SOCK_STREAM,
        SOL_SOCKET=real_socket.SOL_SOCKET,
        SO_KEEPALIVE=real_socket.SO_KEEPALIVE,
        error=OSError,
    )
    monkeypatch.setattr(bms_comm, "socket", fake)
    comm = BMSCommunication(interface="ethernet", ethernet_ip="192.0.2.1", ethernet_port=8899)

    comm.connect()
    comm.connect()

    assert [sock.closed for sock in opened] == [True, False]
    assert comm.bms_connection is opened[1]


class _Link:
    """A TCP link that counts reconnects."""

    def __init__(self):
        self.reconnects = 0

    def problem_note(self, _kind):
        return None

    def reconnect(self):
        self.reconnects += 1
        return True


class _SilentBms:
    """No frame has arrived: every read is empty."""

    def get_analog_data(self, _pack=None):
        return []

    def get_warning_data(self, _pack=None):
        return []


def _poll_without_data(bms_type):
    coordinator = make_coordinator(bms_type=bms_type)
    coordinator.bms = _SilentBms()
    coordinator.bms_comm = _Link()
    coordinator._fetch_data_inner()
    return coordinator.bms_comm.reconnects


def test_jk_poll_without_data_leaves_the_reconnect_to_the_listener():
    assert _poll_without_data("JK_PB") == 0


def test_pace_poll_without_data_still_reconnects():
    assert _poll_without_data("PACE_LV") == 1
