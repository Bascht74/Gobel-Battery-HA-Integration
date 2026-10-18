"""A dongle reboot closes the TCP session. The old socket must not stay in use."""

from custom_components.gobel_battery.bms_comm import BMSCommunication


class _ClosedSocket:
    def recv(self, _size):
        return b""

    def gettimeout(self):
        return 1

    def close(self):
        return None


def test_peer_close_drops_the_socket():
    comm = BMSCommunication(interface="ethernet", ethernet_ip="192.0.2.1", ethernet_port=9999)
    comm.bms_connection = _ClosedSocket()
    assert comm.receive_data() is None
    assert comm.bms_connection is None


class _ResetSocket:
    """Takes the request, then the dongle resets the session."""

    def send(self, data):
        return len(data)

    def recv(self, _size):
        raise ConnectionResetError(104, "Connection reset by peer")

    def gettimeout(self):
        return 1

    def settimeout(self, _timeout):
        return None

    def close(self):
        return None


def _reset_comm():
    comm = BMSCommunication(interface="ethernet", ethernet_ip="192.0.2.1", ethernet_port=9999)
    comm.bms_connection = _ResetSocket()
    reads = []
    receive = comm.receive_data

    def counting_receive(*args, **kwargs):
        reads.append(1)
        return receive(*args, **kwargs)

    comm.receive_data = counting_receive
    return comm, reads


def test_pace_poll_stops_waiting_after_peer_reset():
    from custom_components.gobel_battery.pacebms_rs232 import PACEBMS232

    for name in ("get_analog_data", "get_warning_data"):
        comm, reads = _reset_comm()
        bms = PACEBMS232(comm, object(), "PACE_LV", 5, 0, 0)
        assert getattr(bms, name)() is None
        assert len(reads) == 1
        assert comm.bms_connection is None


def test_pace_config_read_stops_waiting_after_peer_reset():
    from custom_components.gobel_battery.pace_config import GROUPS, read_group
    from custom_components.gobel_battery.pacebms_rs232 import PACEBMS232

    comm, reads = _reset_comm()
    bms = PACEBMS232(comm, object(), "PACE_LV", 5, 0, 0)
    assert read_group(bms, GROUPS[0]) is None
    assert len(reads) == 1
