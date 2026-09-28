"""Writable BMS settings. Created only while expert configuration is enabled."""

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .expert_entity import GobelExpertEntity
from .pace_config import FIELDS

_UNITS = {
    "V": UnitOfElectricPotential.VOLT,
    "A": UnitOfElectricCurrent.AMPERE,
    "°C": UnitOfTemperature.CELSIUS,
    "%": PERCENTAGE,
    "min": UnitOfTime.MINUTES,
}
_CLASSES = {
    "voltage": NumberDeviceClass.VOLTAGE,
    "current": NumberDeviceClass.CURRENT,
    "temperature": NumberDeviceClass.TEMPERATURE,
}


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
            for field in FIELDS:
                entities.append(GobelExpertNumber(coordinator, pack_id, field))
        if entities:
            async_add_entities(entities)

    _add_packs()
    entry.async_on_unload(coordinator.async_add_listener(_add_packs))


class GobelExpertNumber(GobelExpertEntity, NumberEntity):
    """One Pace setting. The name matches the read-only sensor."""

    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator, pack_id, field):
        super().__init__(coordinator, pack_id, field["key"], field["key"])
        self._source = f"view_{field['key']}"
        self._attr_native_min_value = field["min"]
        self._attr_native_max_value = field["max"]
        self._attr_native_step = field["step"]
        self._attr_native_unit_of_measurement = _UNITS.get(field["unit"], field["unit"])
        self._attr_device_class = _CLASSES.get(field["device_class"])
        self._attr_icon = field["icon"]
        self._attr_suggested_display_precision = field["precision"]

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
            await self.coordinator.async_apply_expert_change(self.pack_id, self._key, float(value))
        except RuntimeError as err:
            raise HomeAssistantError(str(err)) from err
