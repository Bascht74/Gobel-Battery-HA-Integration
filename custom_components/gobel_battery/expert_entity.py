"""Shared device identity for expert-mode controls."""

from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity


class GobelExpertEntity(CoordinatorEntity):
    """Configuration control shown only while expert mode is enabled."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator, pack_id, key, translation_key):
        super().__init__(coordinator)
        self.pack_id = pack_id
        self._key = key
        self._attr_has_entity_name = True
        self._attr_translation_key = translation_key
        self._attr_unique_id = f"{coordinator.entry.entry_id}_pack_{pack_id}_expert_{key}"

    @property
    def device_info(self):
        return self.coordinator.pack_device_info(self.pack_id)

    def _section(self, name):
        data = self.coordinator.data or {}
        return next((item for item in data.get(name, []) if item.get("pack_id") == self.pack_id), None)
