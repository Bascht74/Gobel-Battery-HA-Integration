"""A dongle reboot closes the TCP session. The old socket must not stay in use."""

import sys
import types

sys.modules.setdefault("serial", types.ModuleType("serial"))

from bms_comm import BMSCommunication


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
