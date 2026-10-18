"""The coordinator is tied to its config entry explicitly (Home Assistant requires that for Core)."""

from fake_hass import make_coordinator


def test_coordinator_knows_its_config_entry():
    coordinator = make_coordinator()
    assert coordinator.config_entry is coordinator.entry
    assert coordinator.config_entry.entry_id == "entry1"
