"""Expert-mode actions. The BMS clock sensor stays visible either way."""

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

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
        pack_ids = [0] if not packs and not registered else [
            pack.get("pack_id", 0) for pack in packs if pack.get("pack_id", 0) not in registered
        ]
        entities = []
        for pack_id in pack_ids:
            if pack_id in registered or not coordinator.owns_configuration(pack_id):
                continue
            registered.add(pack_id)
            entities.append(GobelSetClockButton(coordinator, pack_id))
        if entities:
            async_add_entities(entities)

    _add_packs()
    entry.async_on_unload(coordinator.async_add_listener(_add_packs))


class GobelSetClockButton(GobelExpertEntity, ButtonEntity):
    """Write the current local time into the BMS clock."""

    def __init__(self, coordinator, pack_id):
        super().__init__(coordinator, pack_id, "set_clock", "set_bms_clock")
        self._attr_icon = "mdi:clock-check"

    async def async_press(self):
        moment = dt_util.now().replace(microsecond=0, tzinfo=None)
        try:
            await self.coordinator.async_apply_expert_change(self.pack_id, "set_clock", moment)
        except RuntimeError as err:
            raise HomeAssistantError(str(err)) from err
