"""The Gobel Battery Monitor integration."""
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .coordinator import GobelBatteryUpdateCoordinator
from .mode_cleanup import stale_unique_ids

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

    try:
        # Run the synchronous driver initialization
        if not await coordinator.async_setup():
            raise ConfigEntryNotReady(f"Failed to connect to BMS for {entry.title}")

        # Fetch initial data so entities have state on startup
        await coordinator.async_config_entry_first_refresh()
    except Exception:
        # A retry builds a new coordinator. Close this one's port and listener thread first.
        await hass.async_add_executor_job(coordinator.shutdown)
        raise

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    _remove_other_mode_entities(hass, entry, coordinator)

    # Forward setup to the sensor and binary_sensor platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


def _remove_other_mode_entities(hass: HomeAssistant, entry: ConfigEntry, coordinator) -> None:
    """Drop what the changeable-settings option replaced, in either direction."""
    registry = er.async_get(hass)
    entries = er.async_entries_for_config_entry(registry, entry.entry_id)
    stale = stale_unique_ids(
        entry.entry_id,
        [item.unique_id for item in entries],
        coordinator.can_write_config,
        coordinator.owns_configuration,
    )
    for item in entries:
        if item.unique_id in stale:
            registry.async_remove(item.entity_id)
    if stale:
        _LOGGER.info("Removed %s entities of the other settings mode", len(stale))


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
