"""Tests import the integration as the package custom_components.gobel_battery.

pyserial is a requirement of the integration but not part of the Home Assistant
test environment. No test opens a serial port, so a stub is enough.
"""

import sys
import types

try:
    import serial  # noqa: F401
except ImportError:
    serial_stub = types.ModuleType("serial")
    serial_stub.Serial = object
    serial_stub.SerialException = OSError
    sys.modules["serial"] = serial_stub
