"""The Gobel Battery Monitor integration."""
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv

from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .coordinator import GobelBatteryUpdateCoordinator
from .pace_config import FIELDS, READ_ONLY

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "binary_sensor", "number", "switch", "select", "button"]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Gobel Battery Monitor component from YAML."""
    hass.data.setdefault(DOMAIN, {})
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Gobel Battery Monitor from a config entry."""
    coordinator = GobelBatteryUpdateCoordinator(hass, entry)
    
    # Run the synchronous driver initialization
    if not await coordinator.async_setup():
        raise ConfigEntryNotReady(f"Failed to connect to BMS for {entry.title}")

    # Fetch initial data so entities have state on startup
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    # Forward setup to the sensor and binary_sensor platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _remove_copied_configuration(hass, entry, coordinator)

    return True


def _remove_copied_configuration(hass, entry, coordinator):
    """Drop settings that were copied from the master onto the other packs."""
    if coordinator.battery_port == "rs485":
        return
    copied = {field["key"] for field in FIELDS}
    copied.update(field["key"] for field in READ_ONLY)
    copied.add("limiter_gear")
    registry = er.async_get(hass)
    prefix = f"{entry.entry_id}_pack_"
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        unique_id = entity.unique_id or ""
        if not unique_id.startswith(prefix):
            continue
        pack_text, _, metric = unique_id[len(prefix):].partition("_")
        if not pack_text.isdigit() or coordinator.owns_configuration(int(pack_text)):
            continue
        if "_expert_" in unique_id or metric in copied:
            registry.async_remove(entity.entity_id)


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload when options or reconfigure change the entry."""
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_save_energy()
        # Release socket/serial/background threads
        await hass.async_add_executor_job(coordinator.shutdown)

    return unload_ok
