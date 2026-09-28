"""Writable BMS limits. Created only while expert configuration is enabled."""

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfElectricCurrent
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .expert_entity import GobelExpertEntity

NUMBERS = (
    ("charge_current_alarm", "Charge Current Alarm", "view_charge_current_alarm"),
    ("charge_current_limit", "Charge Current Limit", "view_charge_current_limit"),
    ("discharge_current_alarm", "Discharge Current Alarm", "view_discharge_current_alarm"),
    ("discharge_current_limit", "Discharge Current Limit", "view_discharge_current_limit"),
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
        packs = (coordinator.data or {}).get("analog", [])
        pack_ids = [0] if not packs and not registered else [
            pack.get("pack_id", 0) for pack in packs if pack.get("pack_id", 0) not in registered
        ]
        entities = []
        for pack_id in pack_ids:
            if pack_id in registered:
                continue
            registered.add(pack_id)
            for key, name, source in NUMBERS:
                entities.append(GobelExpertNumber(coordinator, pack_id, key, name, source))
        if entities:
            async_add_entities(entities)

    _add_packs()
    entry.async_on_unload(coordinator.async_add_listener(_add_packs))


class GobelExpertNumber(GobelExpertEntity, NumberEntity):
    """Positive ampere threshold written back to the BMS."""

    _attr_native_min_value = 1
    _attr_native_max_value = 300
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:current-dc"

    def __init__(self, coordinator, pack_id, key, name, source):
        super().__init__(coordinator, pack_id, key, name)
        self._source = source

    @property
    def available(self):
        return super().available and self._section("analog") is not None

    @property
    def native_value(self):
        pack = self._section("analog")
        if not pack:
            return None
        value = pack.get(self._source)
        return None if value is None else float(value)

    async def async_set_native_value(self, value: float):
        try:
            await self.coordinator.async_apply_expert_change(self.pack_id, self._key, int(value))
        except RuntimeError as err:
            raise HomeAssistantError(str(err)) from err
