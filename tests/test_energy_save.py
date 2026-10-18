"""The energy file is written once a minute, not after every 5 s poll.

17,280 writes a day per battery wear out an SD card. Unload and Home Assistant
stop still write at once (async_unload_entry and a stop listener in __init__.py).
"""

from types import SimpleNamespace

from custom_components.gobel_battery import coordinator as coordinator_module
from fake_hass import make_coordinator


class _Store:
    def __init__(self):
        self.delayed_saves = 0

    def async_delay_save(self, data_func, delay=0):
        self.delayed_saves += 1
        assert data_func() == {"packs": {}}


def test_three_minutes_of_5s_polls_write_three_times(monkeypatch):
    clock = SimpleNamespace(now=1000.0)
    monkeypatch.setattr(coordinator_module, "time", SimpleNamespace(monotonic=lambda: clock.now))
    coordinator = make_coordinator()
    coordinator._store = _Store()

    for _poll in range(36):  # 36 polls x 5 s = 180 s
        coordinator._schedule_energy_save()
        clock.now += 5

    assert coordinator._store.delayed_saves == 3
