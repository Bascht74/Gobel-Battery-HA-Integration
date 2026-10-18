"""receive_data(timeout=...) must not wait for the 3 s socket timeout when the BMS stays silent.

The Pace poll and the settings read wait for their reply in short steps
(0.4 s and 0.35 s). connect() gives the socket a timeout of 3 s.
"""

import socket
import threading
import time

from custom_components.gobel_battery.bms_comm import BMSCommunication


def _comm_with_peer():
    """A TCP-like link to a fake BMS. The socket timeout is 3 s, as after connect()."""
    ours, bms = socket.socketpair()
    ours.settimeout(3)
    comm = BMSCommunication(interface="ethernet", ethernet_ip="192.0.2.10", ethernet_port=8899)
    comm.bms_connection = ours
    return comm, bms


def test_a_short_timeout_ends_the_read_early():
    """Asked for 0.3 s, the read gives up after about 0.3 s instead of 3 s."""
    comm, _bms = _comm_with_peer()
    started = time.monotonic()
    comm.receive_data(timeout=0.3)
    # 1 s leaves room for a slow test machine and is still far below the 3 s.
    assert time.monotonic() - started < 1.0
    # The socket keeps its own 3 s for the next read without a timeout.
    assert comm.bms_connection.gettimeout() == 3


def test_a_reply_within_the_timeout_is_returned():
    comm, bms = _comm_with_peer()
    bms.sendall(b"~25004600C0000000FDB2\r")
    assert comm.receive_data(timeout=0.3) == "~25004600C0000000FDB2"
    assert comm.bms_connection.gettimeout() == 3


def test_a_reply_split_in_two_parts_comes_back_whole():
    """The gateway can send one frame in two TCP parts.

    The read waits 0.4 s. The first part comes at 0.2 s, inside that wait.
    The rest comes at 0.6 s, after it. The read waits for the rest
    instead of returning half a frame.
    """
    comm, bms = _comm_with_peer()
    frame = b"~25004600C0000000FDB2\r"
    threading.Timer(0.2, bms.sendall, args=(frame[:10],)).start()
    threading.Timer(0.6, bms.sendall, args=(frame[10:],)).start()
    assert comm.receive_data(timeout=0.4) == "~25004600C0000000FDB2"
    assert comm.bms_connection.gettimeout() == 3
