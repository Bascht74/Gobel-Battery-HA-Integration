"""Build the coordinator without a running Home Assistant.

The tests only call the coordinator's own methods, which never touch the event loop.
"""

from types import SimpleNamespace

from custom_components.gobel_battery.coordinator import GobelBatteryUpdateCoordinator


def make_entry(bms_type="PACE_LV", battery_port="rs232", connection_type="ethernet", **options):
    """A config entry as the setup flow stores it, with optional options."""
    return SimpleNamespace(
        entry_id="entry1",
        data={
            "device_name": "Gobel Battery",
            "bms_type": bms_type,
            "connection_type": connection_type,
            "battery_port": battery_port,
            "ip_address": "192.0.2.10",
            "ip_port": 8899,
        },
        options=options,
        async_on_unload=lambda _callback: None,
    )


def make_coordinator(**entry_values):
    hass = SimpleNamespace(data={}, config=SimpleNamespace(config_dir="/nonexistent"))
    return GobelBatteryUpdateCoordinator(hass, make_entry(**entry_values))
