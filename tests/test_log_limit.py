"""A dead dongle fails every poll. The log gets one connection message a minute."""

import logging
import socket as real_socket
import types

from custom_components.gobel_battery import bms_comm
from custom_components.gobel_battery.bms_comm import BMSCommunication


class _Clock:
    now = 1000.0

    def __call__(self):
        return self.now


class _Dongle:
    """Accepts the connection and resets it, the way the dongle has behaved since 30.09."""

    healthy = False
    opened = 0

    def socket(self, *_args):
        self.opened += 1
        return _Socket(self, self.opened)


class _Socket:
    def __init__(self, dongle, number):
        self.dongle = dongle
        self.number = number

    def settimeout(self, _timeout):
        return None

    def gettimeout(self):
        return 1

    def setsockopt(self, *_args):
        return None

    def connect(self, _address):
        if not self.dongle.healthy and self.number % 3 == 0:
            raise ConnectionResetError(104, "Connection reset by peer")

    def send(self, data):
        if not self.dongle.healthy and self.number % 3 == 1:
            raise BrokenPipeError(32, "Broken pipe")
        return len(data)

    def recv(self, _size):
        if self.dongle.healthy:
            return b"~25014600\r"
        raise ConnectionResetError(104, "Connection reset by peer")

    def close(self):
        return None


def _comm(monkeypatch, clock, dongle):
    fake = types.SimpleNamespace(
        socket=dongle.socket,
        AF_INET=real_socket.AF_INET,
        SOCK_STREAM=real_socket.SOCK_STREAM,
        SOL_SOCKET=real_socket.SOL_SOCKET,
        SO_KEEPALIVE=real_socket.SO_KEEPALIVE,
        error=OSError,
        timeout=TimeoutError,
    )
    monkeypatch.setattr(bms_comm, "socket", fake)
    monkeypatch.setattr(bms_comm, "monotonic", clock)
    comm = BMSCommunication(interface="ethernet", ethernet_ip="192.0.2.1", ethernet_port=8899)
    assert comm.connect()
    return comm


def _poll(comm, bms, clock, caplog, seconds):
    """Five second polls like the coordinator, with its reopen every 15 seconds."""
    lines = []
    start = clock.now
    while clock.now - start < seconds:
        caplog.clear()
        bms.get_analog_data()
        bms.get_warning_data()
        if (clock.now - start) % 15 == 0:
            comm.reconnect()
        lines += [(clock.now, record) for record in caplog.records if record.levelno >= logging.WARNING]
        clock.now += 5
    return lines


def test_outage_logs_one_line_a_minute(monkeypatch, caplog):
    from custom_components.gobel_battery.pacebms_rs232 import PACEBMS232

    clock, dongle = _Clock(), _Dongle()
    comm = _comm(monkeypatch, clock, dongle)
    bms = PACEBMS232(comm, object(), "PACE_LV", 5, 0, 0)

    lines = _poll(comm, bms, clock, caplog, 300)
    times = [when for when, record in lines if "again" not in record.getMessage()]

    assert 1 <= len(times) <= 5
    assert all(later - earlier >= 60 for earlier, later in zip(times, times[1:]))
    assert any("more connection messages since the last report" in record.getMessage() for _, record in lines)


def test_recovery_logs_one_line(monkeypatch, caplog):
    from custom_components.gobel_battery.pacebms_rs232 import PACEBMS232

    clock, dongle = _Clock(), _Dongle()
    comm = _comm(monkeypatch, clock, dongle)
    bms = PACEBMS232(comm, object(), "PACE_LV", 5, 0, 0)
    _poll(comm, bms, clock, caplog, 120)

    dongle.healthy = True
    comm.reconnect()
    caplog.clear()
    for _ in range(10):
        assert comm.send_data(b"~25014642E00201FD35\r")
        assert comm.receive_data(timeout=0.1) == "~25014600"
        clock.now += 5

    again = [record.getMessage() for record in caplog.records if "again" in record.getMessage()]
    assert again == ["Receiving data from BMS 192.0.2.1:8899 again"]


def test_new_outage_after_a_quiet_minute_logs_at_once(monkeypatch, caplog):
    clock, dongle = _Clock(), _Dongle()
    comm = _comm(monkeypatch, clock, dongle)
    comm.bms_connection = None
    comm.disconnect()
    comm.disconnect()
    clock.now += 61
    comm.disconnect()

    lines = [record.getMessage() for record in caplog.records if "No active connection" in record.getMessage()]
    assert lines == ["No active connection to disconnect.", "No active connection to disconnect. (1 more connection messages since the last report)"]


def test_each_connection_keeps_its_own_count(monkeypatch, caplog):
    clock, dongle = _Clock(), _Dongle()
    first = _comm(monkeypatch, clock, dongle)
    second = BMSCommunication(interface="ethernet", ethernet_ip="192.0.2.2", ethernet_port=8899)
    first.bms_connection = None
    second.bms_connection = None
    first.disconnect()
    second.disconnect()

    assert len([record for record in caplog.records if "No active connection" in record.getMessage()]) == 2
