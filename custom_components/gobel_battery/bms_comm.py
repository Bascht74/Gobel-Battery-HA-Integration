import serial
import socket
import logging
import threading
from time import monotonic

# A dead link fails every poll. Connection problems are logged once per this many seconds.
PROBLEM_LOG_SECONDS = 60

class BMSCommunication:
    def __init__(self, interface='serial', serial_port=None, baud_rate=None, ethernet_ip=None, ethernet_port=None,buffer_size=1024,debug=0):
        self.interface = interface
        self.serial_port = serial_port
        self.baud_rate = baud_rate
        self.ethernet_ip = ethernet_ip
        self.ethernet_port = ethernet_port
        self.buffer_size = buffer_size
        self.bms_connection = None
        self._tcp_buffer = b''
        self._problem_log = {}
        self._log_lock = threading.Lock()
        self._link_down = False

        # Configure logging
        logging.basicConfig(level=logging.DEBUG if debug else logging.INFO,
                            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(__name__)

    def _repeat_note(self, key):
        """None inside the minute after the last line under this key, else a suffix that counts the dropped ones."""
        # The JK listener thread and the poll can report at the same time
        with self._log_lock:
            now = monotonic()
            last = self._problem_log.get(key)
            if last and now - last[0] < PROBLEM_LOG_SECONDS:
                last[1] += 1
                return None
            self._problem_log[key] = [now, 0]
            return f" ({last[1]} more connection messages since the last report)" if last and last[1] else ""

    def problem_note(self, kind):
        """Gate for a connection problem line: log it only when this returns a string, and append that.
        All kinds share one gate, so a dead link writes one line a minute."""
        self._link_down = True
        return self._repeat_note("problem")

    def link_works(self):
        """One line when data arrives again after a connection problem."""
        if not self._link_down:
            return
        self._link_down = False
        note = self._repeat_note("link_works")
        if note is not None:
            peer = f"{self.ethernet_ip}:{self.ethernet_port}" if self.interface in ['ethernet', 'wifi'] else self.serial_port
            self.logger.warning(f"Receiving data from BMS {peer} again{note}")

    def _close_existing(self):
        """Close a connection that is still open, so a new connect() does not leave it behind."""
        if self.bms_connection is None:
            return
        try:
            self.bms_connection.close()
        except Exception as e:
            self.logger.debug(f"Error closing the previous BMS connection: {e}")
        self.bms_connection = None

    def connect(self):
        # Dongles that accept only one client refuse the new session while the old one is open.
        self._close_existing()
        if self.interface == 'serial' and self.serial_port and self.baud_rate:
            try:
                self.logger.info(f"Trying to connect BMS over {self.serial_port}:{self.baud_rate}")
                self.bms_connection = serial.Serial(self.serial_port, self.baud_rate, timeout=3)
                self.logger.info(f"Connected to BMS over serial port: {self.serial_port} with baud rate: {self.baud_rate}")
                self.logger.info("Please ensure the Baud Rate is correctly set. An incorrect baud rate may not raise an immediate error, but it can lead to communication failures or corrupted data.")

                return self.bms_connection
            except serial.SerialException as e:
                if (note := self.problem_note("connect")) is not None:
                    self.logger.error(f"Serial connection error: {e}{note}")
                return None
        elif self.interface in ['ethernet', 'wifi'] and self.ethernet_ip and self.ethernet_port:
            try:
                self.logger.info(f"Trying to connect BMS over {self.ethernet_ip}:{self.ethernet_port}")
                self.bms_connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.bms_connection.settimeout(3)
                self.bms_connection.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                self.bms_connection.connect((self.ethernet_ip, self.ethernet_port))
                self._tcp_buffer = b''
                self.logger.info(f"Connected to BMS over Ethernet: {self.ethernet_ip}:{self.ethernet_port}")
                return self.bms_connection
            except socket.error as e:
                if (note := self.problem_note("connect")) is not None:
                    self.logger.error(f"Ethernet connection error: {e}{note}")
                return None
        else:
            self.logger.error("Invalid parameters or interface selection.")
            return None


    def disconnect(self):
        if self.bms_connection:
            if self.interface == 'serial':
                try:
                    self.bms_connection.close()
                    self.logger.debug(f"Disconnected from BMS over serial port: {self.serial_port}")
                except serial.SerialException as e:
                    self.logger.error(f"Error while disconnecting serial connection: {e}")
            
            elif self.interface in ['ethernet', 'wifi']:
                try:
                    self.bms_connection.close()
                    self.logger.debug(f"Disconnected from BMS over Ethernet: {self.ethernet_ip}:{self.ethernet_port}")
                except socket.error as e:
                    self.logger.error(f"Error while disconnecting Ethernet connection: {e}")
            
            # Set connection to None after closing it.
            self.bms_connection = None
        elif (note := self.problem_note("no_connection")) is not None:
            self.logger.warning(f"No active connection to disconnect.{note}")

    def reconnect(self):
        """Drop a dead socket and open a new one. A dongle reboot leaves the old one open."""
        self.disconnect()
        self._tcp_buffer = b""
        return bool(self.connect())

    def send_data(self, data):
        try:
            # Ensure data is in bytes format
            if isinstance(data, str):
                data = data.encode()  # Convert string to bytes if necessary

            if not self.bms_connection and not self.connect():
                return False

            # Check if the connection is a socket (Ethernet)
            if hasattr(self.bms_connection, 'send'):
                sent_bytes = self.bms_connection.send(data)
                self.logger.debug(f"Sent data via TCP: {data.hex().upper()}")
                
            # Check if the connection is a serial connection
            elif hasattr(self.bms_connection, 'write'):
                sent_bytes = self.bms_connection.write(data)
                self.logger.debug(f"Sent data via serial: {data.hex().upper()}")
            else:
                raise ValueError("Unsupported connection type")
            return True

        except Exception as e:
            if (note := self.problem_note("send")) is not None:
                self.logger.error(f"Error sending data to BMS: {e}{note}")
            self.reconnect()
            return False

    def receive_data(self, return_raw=False, timeout=None):
        try:
            if not self.bms_connection:
                raise ValueError("No active connection")

            # Check if the connection is a serial connection
            if hasattr(self.bms_connection, 'readline'):
                if hasattr(self.bms_connection, 'read_until'):
                    raw_data = self.bms_connection.read_until(b'\r')
                else:
                    raw_data = self.bms_connection.readline()
                if raw_data:
                    self.link_works()
                if return_raw:
                    return raw_data
                else:
                    received_data = raw_data.decode().strip()
            # Check if the connection is a socket (Ethernet)
            elif hasattr(self.bms_connection, 'recv'):
                if return_raw:
                    # For raw data, use dedicated TCP Modbus receiving logic
                    raw_data = self._receive_tcp_modbus_response()
                    if raw_data:
                        self.link_works()
                        self.logger.debug(f"Received raw data (hex): {raw_data.hex().upper()}")
                        return raw_data
                    else:
                        return None
                else:
                    # Original string receiving method, for other BMS.
                    # We maintain a buffer in self._tcp_buffer and read until b'\r' is received.
                    if not hasattr(self, '_tcp_buffer'):
                        self._tcp_buffer = b''
                    
                    peer_closed = False
                    import time
                    start_time = time.time()
                    socket_timeout = self.bms_connection.gettimeout()
                    timeout = timeout if timeout is not None else (socket_timeout or 3.0)
                    
                    while b'\r' not in self._tcp_buffer:
                        remaining = timeout - (time.time() - start_time)
                        if remaining <= 0:
                            break
                        try:
                            # Read chunks of data. Until the reply starts, a short timeout from the caller
                            # also limits each recv(). Once it has started, recv() waits with the socket's
                            # own timeout, so a frame split over two TCP parts still arrives whole.
                            if self._tcp_buffer:
                                self.bms_connection.settimeout(socket_timeout)
                            else:
                                self.bms_connection.settimeout(min(remaining, socket_timeout or remaining))
                            chunk = self.bms_connection.recv(4096)
                            if not chunk:
                                peer_closed = True
                                break
                            self._tcp_buffer += chunk
                        except socket.timeout:
                            break
                        except Exception as e:
                            if (note := self.problem_note("read")) is not None:
                                self.logger.error(f"Error reading socket: {e}{note}")
                            peer_closed = True
                            break
                    # Each error above ends the loop, so later reads always get the socket's own timeout back.
                    self.bms_connection.settimeout(socket_timeout)

                    if peer_closed:
                        if (note := self.problem_note("peer_closed")) is not None:
                            self.logger.warning(f"BMS closed the TCP connection{note}")
                        self.disconnect()
                        self._tcp_buffer = b""
                        return None
                    
                    if b'\r' in self._tcp_buffer:
                        idx = self._tcp_buffer.index(b'\r')
                        raw_data = self._tcp_buffer[:idx + 1]
                        self._tcp_buffer = self._tcp_buffer[idx + 1:]
                    else:
                        raw_data = self._tcp_buffer
                        self._tcp_buffer = b''
                    if raw_data:
                        self.link_works()
                    
                    received_data = raw_data.decode('ascii', errors='ignore').strip()
            else:
                raise ValueError("Unsupported connection type")

            if not return_raw:
                self.logger.debug(f"Received data from BMS: {received_data}")
                return received_data
        except Exception as e:
            # Log the raw data when there is a decoding error
            if 'raw_data' in locals():
                self.logger.error(f"Error receiving data from BMS: {e}. Raw data: {raw_data}")
                self.logger.error(f"Raw data (hex): {raw_data.hex()}")
            else:
                if (note := self.problem_note("receive")) is not None:
                    self.logger.warning(f"No data received from BMS: {e}{note}")
                self.disconnect()
            return None

    def _receive_tcp_modbus_response(self):
        """
        A dedicated method for receiving TCP Modbus RTU responses.
        """
        try:
            import time

            # Wait for BMS processing time after sending
            time.sleep(0.1)

            # Receive data
            all_data = b''
            max_attempts = 5
            attempt = 0

            while attempt < max_attempts:
                try:
                    # Set timeout
                    original_timeout = self.bms_connection.gettimeout()
                    self.bms_connection.settimeout(1.0)

                    chunk = self.bms_connection.recv(1024)

                    # Restore original timeout setting
                    self.bms_connection.settimeout(original_timeout)

                    if chunk:
                        all_data += chunk
                        self.logger.debug(f"Received {len(chunk)} bytes, total {len(all_data)} bytes")

                        # Check if a complete Modbus response has been received
                        if len(all_data) >= 3:
                            device_addr, function_code, byte_count = all_data[0], all_data[1], all_data[2]
                            expected_length = 3 + byte_count + 2  # Header + Data + CRC

                            if len(all_data) >= expected_length:
                                complete_response = all_data[:expected_length]
                                self.logger.debug(f"Successfully received complete Modbus response: {expected_length} bytes")
                                return complete_response

                        # Wait a short while for more data
                        time.sleep(0.05)
                    else:
                        time.sleep(0.1)

                except socket.timeout:
                    # Timeout is normal, continue trying
                    pass
                except Exception as e:
                    self.logger.warning(f"Error while receiving data: {e}")

                attempt += 1

            if all_data:
                self.logger.debug(f"Received data, but it might be incomplete: {len(all_data)} bytes")
                return all_data
            else:
                self.logger.warning("No data received")
                return None

        except Exception as e:
            self.logger.error(f"Error receiving TCP Modbus response: {e}")
            return None

    def flush(self):
        """
        Flush any stale/buffered data from the connection (serial input buffer or TCP socket buffer)
        before sending a new command.
        """
        if not self.bms_connection:
            return
        try:
            if hasattr(self.bms_connection, 'reset_input_buffer'):
                self.bms_connection.reset_input_buffer()
                self.logger.debug("Flushed serial input buffer")
            elif hasattr(self.bms_connection, 'recv'):
                import socket as _socket
                self._tcp_buffer = b''
                original_timeout = self.bms_connection.gettimeout()
                self.bms_connection.settimeout(0.01)
                flushed = 0
                while True:
                    try:
                        chunk = self.bms_connection.recv(4096)
                        if not chunk:
                            break
                        flushed += len(chunk)
                    except _socket.timeout:
                        break
                    except Exception:
                        break
                self.bms_connection.settimeout(original_timeout)
                if flushed > 0:
                    self.logger.debug(f"Flushed {flushed} stale bytes from TCP socket buffer")
        except Exception as e:
            self.logger.debug(f"Buffer flush error: {e}")

    def flush_jkbms_buffer(self):
        """
        Flush any stale/buffered data from the socket before sending a new command.
        The JK BMS continuously broadcasts 55AA frames, so we need to discard
        any pre-existing data in the TCP buffer to avoid reading stale frames.
        """
        import socket as _socket
        if not self.bms_connection:
            return
        try:
            if hasattr(self.bms_connection, 'reset_input_buffer'):
                self.bms_connection.reset_input_buffer()
                self.logger.debug("JK BMS: Flushed serial input buffer")
                return

            original_timeout = self.bms_connection.gettimeout()
            self.bms_connection.settimeout(0.05)
            flushed = 0
            while True:
                try:
                    chunk = self.bms_connection.recv(4096)
                    if not chunk:
                        break
                    flushed += len(chunk)
                except _socket.timeout:
                    break
            self.bms_connection.settimeout(original_timeout)
            if flushed > 0:
                self.logger.debug(f"JK BMS: Flushed {flushed} stale bytes from input buffer")
        except Exception as e:
            self.logger.debug(f"JK BMS: Buffer flush note: {e}")
            try:
                self.bms_connection.settimeout(original_timeout)
            except Exception:
                pass

    def receive_jkbms_raw(self):
        """
        Receive raw TCP data for JK BMS communication.
        Reads all available bytes from TCP without Modbus framing assumptions.
        The JK BMS responds with JK proprietary 55AA frames which need to be parsed
        at the protocol level, not here.
        Used in command-based mode (diagnose_jkbms.py).
        """
        try:
            import time

            # Wait for BMS processing time before reading
            time.sleep(0.3)

            all_data = b''
            idle_timeout = 5   # Consecutive empty reads before stopping
            idle_count = 0
            got_data = False

            while True:
                try:
                    if hasattr(self.bms_connection, 'read'):
                        original_timeout = self.bms_connection.timeout
                        self.bms_connection.timeout = 0.2
                        chunk = self.bms_connection.read(2048)
                        self.bms_connection.timeout = original_timeout
                    else:
                        original_timeout = self.bms_connection.gettimeout()
                        self.bms_connection.settimeout(0.2)
                        chunk = self.bms_connection.recv(2048)
                        self.bms_connection.settimeout(original_timeout)

                    if chunk:
                        all_data += chunk
                        self.logger.debug(f"JK BMS: Received {len(chunk)} bytes, total {len(all_data)} bytes")
                        got_data = True
                        idle_count = 0  # Reset idle counter
                    else:
                        idle_count += 1

                except socket.timeout:
                    idle_count += 1

                except Exception as e:
                    self.logger.warning(f"JK BMS receive error: {e}")
                    idle_count += 1

                # After getting data, allow a few idle cycles for trailing chunks
                if got_data and idle_count >= idle_timeout:
                    break
                # If no data at all after initial wait + max attempts, give up
                if not got_data and idle_count >= 40:  # ~8 seconds total
                    break

                time.sleep(0.05)

            if all_data:
                self.logger.debug(f"JK BMS: Total received {len(all_data)} bytes")
                return all_data
            else:
                self.logger.warning("JK BMS: No data received")
                return None

        except Exception as e:
            self.logger.error(f"JK BMS receive error: {e}")
            return None

    def receive_jkbms_passive(self, read_timeout=2.0):
        """
        Passively read JK BMS broadcast data without sending any command.
        The JK BMS continuously broadcasts 55AA frames every ~200ms.

        Args:
            read_timeout: Maximum time in seconds to wait for initial data.
                          Once data starts arriving, reads until idle.
        Returns:
            bytes: All data accumulated, or None if no data received.
        """
        try:
            import time
            import socket as _socket

            start_time = time.time()
            all_data = b''
            idle_count = 0
            got_data = False
            idle_timeout = 5

            while time.time() - start_time < read_timeout:
                if not self.bms_connection:
                    if (note := self.problem_note("jk_no_connection")) is not None:
                        self.logger.warning(f"JK BMS: No connection, attempting reconnect...{note}")
                    if not self.connect():
                        time.sleep(0.5)
                        continue

                try:
                    is_serial = hasattr(self.bms_connection, 'read')
                    if is_serial:
                        original_timeout = self.bms_connection.timeout
                        self.bms_connection.timeout = 0.2
                        chunk = self.bms_connection.read(4096)
                        self.bms_connection.timeout = original_timeout
                    else:
                        original_timeout = self.bms_connection.gettimeout()
                        self.bms_connection.settimeout(0.2)
                        chunk = self.bms_connection.recv(4096)
                        self.bms_connection.settimeout(original_timeout)

                    if chunk:
                        all_data += chunk
                        self.logger.debug(f"JK BMS: Received {len(chunk)} bytes, total {len(all_data)} bytes")
                        got_data = True
                        idle_count = 0
                    else:
                        if is_serial:
                            # For serial, b'' just means read timeout, no data available.
                            # This is normal, not a connection close.
                            idle_count += 1
                        else:
                            # recv() returned b'' — server closed the TCP connection
                            if (note := self.problem_note("jk_peer_closed")) is not None:
                                self.logger.warning(f"JK BMS: Connection closed by remote (recv=b''), reconnecting...{note}")
                            try:
                                self.bms_connection.close()
                            except Exception:
                                pass
                            self.bms_connection = None
                            if self.connect():
                                self.logger.info("JK BMS: Reconnected successfully")
                                idle_count = 0
                            else:
                                if (note := self.problem_note("jk_reconnect")) is not None:
                                    self.logger.error(f"JK BMS: Reconnect failed, aborting read{note}")
                                break

                except _socket.timeout:
                    idle_count += 1

                except Exception as e:
                    if (note := self.problem_note("jk_read")) is not None:
                        self.logger.warning(f"JK BMS receive error: {e}{note}")
                    self.disconnect()
                    idle_count += 1

                if got_data and idle_count >= idle_timeout:
                    break

                time.sleep(0.05)

            if all_data:
                self.link_works()
                self.logger.debug(f"JK BMS: Passively received {len(all_data)} bytes")
                return all_data
            else:
                self.logger.debug("JK BMS: No data in passive read")
                return None

        except Exception as e:
            self.logger.error(f"JK BMS passive receive error: {e}")
            return None

