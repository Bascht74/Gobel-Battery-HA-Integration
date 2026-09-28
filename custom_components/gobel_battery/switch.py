"""Writable BMS switches. Created only while expert configuration is enabled."""

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .expert_entity import GobelExpertEntity

SWITCHES = (
    ("charge_switch", "Charge Enabled", "status_charge_enabled", "mdi:battery-charging"),
    ("discharge_switch", "Discharge Enabled", "status_discharge_enabled", "mdi:battery-arrow-down"),
    ("limiter_switch", "Charge Current Limiter", "status_current_limit_enabled", "mdi:speedometer"),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    if not coordinator.can_write_config:
        return

    registered = set()

    @callback
    def _add_packs():
        packs = (coordinator.data or {}).get("warning", [])
        pack_ids = [0] if not packs and not registered else [
            pack.get("pack_id", 0) for pack in packs if pack.get("pack_id", 0) not in registered
        ]
        entities = []
        for pack_id in pack_ids:
            if pack_id in registered:
                continue
            registered.add(pack_id)
            for key, name, flag, icon in SWITCHES:
                entities.append(GobelExpertSwitch(coordinator, pack_id, key, name, flag, icon))
        if entities:
            async_add_entities(entities)

    _add_packs()
    entry.async_on_unload(coordinator.async_add_listener(_add_packs))


class GobelExpertSwitch(GobelExpertEntity, SwitchEntity):
    """MOSFET or charge-limiter switch."""

    def __init__(self, coordinator, pack_id, key, name, flag, icon):
        super().__init__(coordinator, pack_id, key, name)
        self._flag = flag
        self._attr_icon = icon

    @property
    def available(self):
        pack = self._section("warning")
        return super().available and isinstance((pack or {}).get("instruction_state"), dict)

    @property
    def is_on(self):
        pack = self._section("warning")
        if not pack:
            return None
        return bool(pack.get("instruction_state", {}).get(self._flag))

    async def async_turn_on(self, **kwargs):
        await self._set(True)

    async def async_turn_off(self, **kwargs):
        await self._set(False)

    async def _set(self, value):
        try:
            await self.coordinator.async_apply_expert_change(self.pack_id, self._key, value)
        except RuntimeError as err:
            raise HomeAssistantError(str(err)) from err
