"""Writable BMS selects. Created only while expert configuration is enabled."""

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .expert_entity import GobelExpertEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    if not coordinator.can_write_config:
        return

    registered = set()

    @callback
    def _add_packs():
        packs = (coordinator.data or {}).get("analog", [])
        entities = []
        for pack in packs:
            pack_id = pack.get("pack_id", 0)
            if pack_id in registered or not coordinator.owns_configuration(pack_id):
                continue
            if pack_id not in coordinator._limiter_gear and pack.get("view_limiter_start_current") is None:
                continue
            registered.add(pack_id)
            entities.append(GobelLimiterGearSelect(coordinator, pack_id))
        if entities:
            async_add_entities(entities)

    _add_packs()
    entry.async_on_unload(coordinator.async_add_listener(_add_packs))


class GobelLimiterGearSelect(GobelExpertEntity, SelectEntity):
    """High or low gear of the Pace charge-current limiter."""

    _attr_options = ["high", "low"]
    _attr_icon = "mdi:speedometer"

    def __init__(self, coordinator, pack_id):
        super().__init__(coordinator, pack_id, "limiter_gear", "limiter_gear")

    @property
    def current_option(self):
        return self.coordinator._limiter_gear.get(self.pack_id)

    async def async_select_option(self, option: str):
        try:
            await self.coordinator.async_apply_expert_change(self.pack_id, "limiter_gear", option)
        except RuntimeError as err:
            raise HomeAssistantError(str(err)) from err
