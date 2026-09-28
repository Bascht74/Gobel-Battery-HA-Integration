"""Binary sensor platform for the Gobel Battery Monitor integration."""
import logging
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import BMS_TYPE_JK_PB, DOMAIN

_LOGGER = logging.getLogger(__name__)

# Metadata: sub-dictionary, key, name, device class, entity category.
# Protection and fault bits stay on the main device page (no category) because
# they use device class PROBLEM. Detailed warnings and status flags are diagnostic.
BINARY_SENSORS_METADATA = {
    "protect_state_1": {
        "protect_short_circuit": ("Short Circuit Protection", BinarySensorDeviceClass.PROBLEM, None),
        "protect_high_discharge_current": ("Discharge Overcurrent Protection", BinarySensorDeviceClass.PROBLEM, None),
        "protect_high_charge_current": ("Charge Overcurrent Protection", BinarySensorDeviceClass.PROBLEM, None),
        "protect_low_total_voltage": ("Total Under-Voltage Protection", BinarySensorDeviceClass.PROBLEM, None),
        "protect_high_total_voltage": ("Total Over-Voltage Protection", BinarySensorDeviceClass.PROBLEM, None),
        "protect_low_cell_voltage": ("Cell Under-Voltage Protection", BinarySensorDeviceClass.PROBLEM, None),
        "protect_high_cell_voltage": ("Cell Over-Voltage Protection", BinarySensorDeviceClass.PROBLEM, None),
    },
    "protect_state_2": {
        "protect_low_charge_temp": ("Charge Low Temp Protection", BinarySensorDeviceClass.PROBLEM, None),
        "protect_high_charge_temp": ("Charge High Temp Protection", BinarySensorDeviceClass.PROBLEM, None),
        "protect_high_MOS_temp": ("MOS High Temp Protection", BinarySensorDeviceClass.PROBLEM, None),
        "protect_high_discharge_temp": ("Discharge High Temp Protection", BinarySensorDeviceClass.PROBLEM, None),
        "status_fully_charged": ("Fully Charged Status", None, EntityCategory.DIAGNOSTIC),
        "protect_low_env_temp": ("Low Env Temp Protection", BinarySensorDeviceClass.PROBLEM, None),
        "protect_high_env_temp": ("High Env Temp Protection", BinarySensorDeviceClass.PROBLEM, None),
        "protect_low_discharge_temp": ("Discharge Low Temp Protection", BinarySensorDeviceClass.PROBLEM, None),
    },
    "fault_state": {
        "fault_sampling": ("Sampling Fault", BinarySensorDeviceClass.PROBLEM, None),
        "fault_cell": ("Cell Count Mismatch/Fault", BinarySensorDeviceClass.PROBLEM, None),
        "fault_NTC": ("Temperature Sensor Fault", BinarySensorDeviceClass.PROBLEM, None),
        "fault_discharge_MOS": ("Discharge MOS Fault", BinarySensorDeviceClass.PROBLEM, None),
        "fault_charge_MOS": ("Charge MOS Fault", BinarySensorDeviceClass.PROBLEM, None),
    },
    "instruction_state": {
        "status_heating": ("Heating Switch Active", BinarySensorDeviceClass.HEAT, EntityCategory.DIAGNOSTIC),
        "status_charger_avaliable": ("Charger Available", BinarySensorDeviceClass.PLUG, EntityCategory.DIAGNOSTIC),
        "status_reverse_connected": ("Reverse Connected Alert", BinarySensorDeviceClass.PROBLEM, None),
        "status_discharge_enabled": ("Discharge Enabled Status", BinarySensorDeviceClass.POWER, EntityCategory.CONFIG),
        "status_charge_enabled": ("Charge Enabled Status", BinarySensorDeviceClass.POWER, EntityCategory.CONFIG),
        "status_current_limit_enabled": ("Current Limiter Active", BinarySensorDeviceClass.POWER, EntityCategory.CONFIG),
    },
    "control_state": {
        "buzzer_warn_function": ("Buzzer Enabled", None, EntityCategory.CONFIG),
        "led_warn_function": ("LED Alarm Enabled", None, EntityCategory.CONFIG),
    },
    "warn_state_1": {
        "warn_high_discharge_current": ("Discharge Overcurrent Warning", BinarySensorDeviceClass.PROBLEM, EntityCategory.DIAGNOSTIC),
        "warn_high_charge_current": ("Charge Overcurrent Warning", BinarySensorDeviceClass.PROBLEM, EntityCategory.DIAGNOSTIC),
        "warn_low_total_voltage": ("Total Under-Voltage Warning", BinarySensorDeviceClass.PROBLEM, EntityCategory.DIAGNOSTIC),
        "warn_high_total_voltage": ("Total Over-Voltage Warning", BinarySensorDeviceClass.PROBLEM, EntityCategory.DIAGNOSTIC),
        "warn_low_cell_voltage": ("Cell Under-Voltage Warning", BinarySensorDeviceClass.PROBLEM, EntityCategory.DIAGNOSTIC),
        "warn_high_cell_voltage": ("Cell Over-Voltage Warning", BinarySensorDeviceClass.PROBLEM, EntityCategory.DIAGNOSTIC),
    },
    "warn_state_2": {
        "warn_low_SOC": ("Low SOC Warning", BinarySensorDeviceClass.PROBLEM, EntityCategory.DIAGNOSTIC),
        "warn_high_MOS_temp": ("MOS High Temp Warning", BinarySensorDeviceClass.PROBLEM, EntityCategory.DIAGNOSTIC),
        "warn_low_env_temp": ("Low Env Temp Warning", BinarySensorDeviceClass.PROBLEM, EntityCategory.DIAGNOSTIC),
        "warn_high_env_temp": ("High Env Temp Warning", BinarySensorDeviceClass.PROBLEM, EntityCategory.DIAGNOSTIC),
        "warn_low_discharge_temp": ("Discharge Low Temp Warning", BinarySensorDeviceClass.PROBLEM, EntityCategory.DIAGNOSTIC),
        "warn_low_charge_temp": ("Charge Low Temp Warning", BinarySensorDeviceClass.PROBLEM, EntityCategory.DIAGNOSTIC),
        "warn_high_discharge_temp": ("Discharge High Temp Warning", BinarySensorDeviceClass.PROBLEM, EntityCategory.DIAGNOSTIC),
        "warn_high_charge_temp": ("Charge High Temp Warning", BinarySensorDeviceClass.PROBLEM, EntityCategory.DIAGNOSTIC),
    },
}

_NORMAL_WARNING = {"normal", "unknown", "", None}

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    """Set up the binary sensor platform from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    # Track registered pack IDs
    registered_packs = set()

    @callback
    def async_add_pack_binary_sensors():
        """Add binary sensors for newly discovered packs."""
        data = coordinator.data
        warning_packs = data.get("warning", []) if data else []
        
        # Default to pack 0 if no packs are detected yet so entities are visible
        if not warning_packs and not registered_packs:
            pack_ids_to_add = [0]
        else:
            pack_ids_to_add = [p.get("pack_id", 0) for p in warning_packs if p.get("pack_id", 0) not in registered_packs]

        new_entities = []
        for pack_id in pack_ids_to_add:
            if pack_id in registered_packs:
                continue
                
            for sub_dict, sensors in BINARY_SENSORS_METADATA.items():
                if sub_dict == "control_state" and coordinator.bms_type == BMS_TYPE_JK_PB:
                    continue
                for key, (name, device_class, category) in sensors.items():
                    if coordinator.can_write_config and key in (
                        "status_charge_enabled",
                        "status_discharge_enabled",
                        "status_current_limit_enabled",
                    ):
                        continue
                    new_entities.append(
                        GobelBatteryBinarySensor(
                            coordinator, pack_id, sub_dict, key, name, device_class, category
                        )
                    )

            warning_pack = next((p for p in warning_packs if p.get("pack_id") == pack_id), None)
            cell_warnings = (warning_pack or {}).get("cell_voltage_warnings") or []
            temp_warnings = (warning_pack or {}).get("temp_sensor_warnings") or []
            num_cells = len(cell_warnings) or 16
            num_temps = len(temp_warnings) or 4

            for cell_idx in range(1, num_cells + 1):
                new_entities.append(
                    GobelBatteryIndexedWarningSensor(
                        coordinator, pack_id, "cell_voltage_warnings", cell_idx, "Cell", "Voltage Warning"
                    )
                )
            for temp_idx in range(1, num_temps + 1):
                new_entities.append(
                    GobelBatteryIndexedWarningSensor(
                        coordinator, pack_id, "temp_sensor_warnings", temp_idx, "Temperature", "Warning"
                    )
                )

            for key, name in (
                ("balancing_status_passive_1", "Passive Balance 1 Active"),
                ("balancing_status_passive_2", "Passive Balance 2 Active"),
                ("balancing_status_active_1", "Active Balance 1 Active"),
                ("balancing_status_active_2", "Active Balance 2 Active"),
            ):
                new_entities.append(
                    GobelBatteryBalanceSensor(coordinator, pack_id, key, name)
                )
            registered_packs.add(pack_id)
            
        if new_entities:
            async_add_entities(new_entities, update_before_add=True)

    # Initial setup
    async_add_pack_binary_sensors()

    # Listen for future updates
    entry.async_on_unload(
        coordinator.async_add_listener(async_add_pack_binary_sensors)
    )

class GobelBatteryBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor representing a BMS alarm, warning or status state."""

    def __init__(self, coordinator, pack_id, sub_dict, key, name, device_class, category):
        """Initialize binary sensor."""
        super().__init__(coordinator)
        self.pack_id = pack_id
        self._sub_dict = sub_dict
        self._key = key
        self._attr_has_entity_name = True
        self._attr_translation_key = key
        self._attr_unique_id = f"{coordinator.entry.entry_id}_pack_{pack_id}_{sub_dict}_{key}"
        self._attr_device_class = device_class
        self._attr_entity_category = category

    @property
    def device_info(self):
        """Return device info for individual pack child device."""
        display_pack = self.pack_id + (0 if self.coordinator.jk_display_index_start == "00" else 1)
        return {
            "identifiers": {(DOMAIN, f"{self.coordinator.entry.entry_id}_pack_{self.pack_id}")},
            "name": f"{self.coordinator.device_name} Pack {display_pack:02d}",
            "via_device": (DOMAIN, f"{self.coordinator.entry.entry_id}_total"),
        }

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if not super().available:
            return False
        data = self.coordinator.data
        if not data:
            return False
        warning_packs = data.get("warning", [])
        pack_warnings = next((p for p in warning_packs if p.get("pack_id") == self.pack_id), None)
        if not pack_warnings:
            return False
        sub_data = pack_warnings.get(self._sub_dict)
        return isinstance(sub_data, dict) and self._key in sub_data

    @property
    def is_on(self):
        """Return True if the binary sensor is active/triggered."""
        data = self.coordinator.data
        if not data:
            return None
        warning_packs = data.get("warning", [])

        pack_warnings = next((p for p in warning_packs if p.get("pack_id") == self.pack_id), None)
        if not pack_warnings:
            return None

        sub_data = pack_warnings.get(self._sub_dict)
        if not isinstance(sub_data, dict) or self._key not in sub_data:
            return None
        return bool(sub_data.get(self._key))


class GobelBatteryIndexedWarningSensor(CoordinatorEntity, BinarySensorEntity):
    """Per-cell voltage or per-probe temperature warning from the Pace/TDT frame."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, pack_id, list_key, index, label, suffix):
        super().__init__(coordinator)
        self.pack_id = pack_id
        self._list_key = list_key
        self._index = index
        self._attr_has_entity_name = True
        self._attr_translation_key = (
            "cell_voltage_warning" if list_key == "cell_voltage_warnings" else "temperature_warning"
        )
        self._attr_translation_placeholders = {"index": f"{index:02d}"}
        self._attr_unique_id = (
            f"{coordinator.entry.entry_id}_pack_{pack_id}_{list_key}_{index}"
        )

    @property
    def device_info(self):
        display_pack = self.pack_id + (0 if self.coordinator.jk_display_index_start == "00" else 1)
        return {
            "identifiers": {(DOMAIN, f"{self.coordinator.entry.entry_id}_pack_{self.pack_id}")},
            "name": f"{self.coordinator.device_name} Pack {display_pack:02d}",
            "via_device": (DOMAIN, f"{self.coordinator.entry.entry_id}_total"),
        }

    def _pack_warnings(self):
        data = self.coordinator.data
        if not data:
            return None
        return next(
            (p for p in data.get("warning", []) if p.get("pack_id") == self.pack_id),
            None,
        )

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        pack = self._pack_warnings()
        if not pack:
            return False
        values = pack.get(self._list_key) or []
        return self._index - 1 < len(values)

    @property
    def is_on(self):
        pack = self._pack_warnings()
        if not pack:
            return None
        values = pack.get(self._list_key) or []
        if self._index - 1 >= len(values):
            return None
        value = values[self._index - 1]
        if isinstance(value, str):
            return value.strip().lower() not in _NORMAL_WARNING
        return bool(value)


class GobelBatteryBalanceSensor(CoordinatorEntity, BinarySensorEntity):
    """Active when a Pace/TDT balance bitmask or active-balance cell index is non-zero."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, pack_id, key, name):
        super().__init__(coordinator)
        self.pack_id = pack_id
        self._key = key
        self._attr_has_entity_name = True
        self._attr_translation_key = key
        self._attr_unique_id = f"{coordinator.entry.entry_id}_pack_{pack_id}_{key}"
        self._attr_icon = "mdi:scale-balance"

    @property
    def device_info(self):
        display_pack = self.pack_id + (0 if self.coordinator.jk_display_index_start == "00" else 1)
        return {
            "identifiers": {(DOMAIN, f"{self.coordinator.entry.entry_id}_pack_{self.pack_id}")},
            "name": f"{self.coordinator.device_name} Pack {display_pack:02d}",
            "via_device": (DOMAIN, f"{self.coordinator.entry.entry_id}_total"),
        }

    def _pack_warnings(self):
        data = self.coordinator.data
        if not data:
            return None
        return next(
            (p for p in data.get("warning", []) if p.get("pack_id") == self.pack_id),
            None,
        )

    @property
    def available(self) -> bool:
        if not super().available:
            return False
        pack = self._pack_warnings()
        return bool(pack) and self._key in pack

    @property
    def is_on(self):
        pack = self._pack_warnings()
        if not pack or self._key not in pack:
            return None
        try:
            return int(pack.get(self._key) or 0) != 0
        except (TypeError, ValueError):
            return None
