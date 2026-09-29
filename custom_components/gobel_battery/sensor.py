"""Sensor platform for the Gobel Battery Monitor integration."""
import logging
from homeassistant.components.sensor import SensorEntity, SensorStateClass, SensorDeviceClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, BMS_TYPE_JK_PB, BMS_TYPE_PACE_LV, BMS_TYPE_PACE_LV_WIFI
from .measurements import volts_from_millivolts, watts_from_kilowatts
from .pace_config import FIELDS, READ_ONLY

_LOGGER = logging.getLogger(__name__)

_DEVICE_CLASS = {
    "voltage": SensorDeviceClass.VOLTAGE,
    "current": SensorDeviceClass.CURRENT,
    "temperature": SensorDeviceClass.TEMPERATURE,
}


def _pace_configuration_sensors():
    """Read-only copies of the Pace settings. Expert mode replaces them with numbers."""
    return {
        field["key"]: {
            "name": field["name"],
            "key": f"view_{field['key']}",
            "unit": field["unit"],
            "device_class": _DEVICE_CLASS.get(field["device_class"]),
            "state_class": SensorStateClass.MEASUREMENT,
            "icon": field["icon"],
            "category": EntityCategory.CONFIG,
            "precision": field["precision"],
        }
        for field in FIELDS
    }


def _pace_readonly_sensors():
    """Values that stay sensors even in expert mode. They are never written."""
    return {
        field["key"]: {
            "name": field["name"],
            "key": f"view_{field['key']}",
            "unit": field["unit"],
            "device_class": None,
            "state_class": None,
            "icon": field["icon"],
            "category": EntityCategory.CONFIG,
            "precision": field["precision"],
            "read_only": True,
        }
        for field in READ_ONLY
    }

# Predefined metadata for overall and pack sensors.
# entity_category None keeps the value on the device page.
# CONFIG = BMS setpoints, DIAGNOSTIC = detail that is not needed for daily use.
# state_class is what enables long-term statistics. ENERGY + total_increasing
# is what the Energy dashboard can use.
SENSOR_METADATA = {
    "voltage": {
        "name": "Voltage",
        "unit": "V",
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:sine-wave",
        "category": None,
    },
    "current": {
        "name": "Current",
        "unit": "A",
        "device_class": SensorDeviceClass.CURRENT,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:current-dc",
        "category": None,
    },
    "power": {
        "name": "Power",
        "unit": "W",
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:battery-charging",
        "category": None,
        "precision": 1,
    },
    "soc": {
        "name": "SOC",
        "unit": "%",
        "device_class": SensorDeviceClass.BATTERY,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:battery-70",
        "category": None,
    },
    "soh": {
        "name": "SOH",
        "unit": "%",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:battery-plus-variant",
        "category": EntityCategory.DIAGNOSTIC,
    },
    "remain_capacity": {
        "name": "Remaining Capacity",
        "unit": "Ah",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:battery-clock",
        "category": None,
    },
    "full_capacity": {
        "name": "Full Capacity",
        "unit": "Ah",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:battery-high",
        "category": EntityCategory.DIAGNOSTIC,
    },
    "cycle_number": {
        "name": "Cycle Count",
        "unit": "cycles",
        "device_class": None,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "icon": "mdi:battery-sync",
        "category": EntityCategory.DIAGNOSTIC,
    },
    "design_capacity": {
        "name": "Design Capacity",
        "unit": "Ah",
        "device_class": None,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:battery-high",
        "category": EntityCategory.DIAGNOSTIC,
        "precision": 2,
    },
    "cell_voltage_max": {
        "name": "Highest Cell Voltage",
        "unit": "V",
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:align-vertical-top",
        "category": EntityCategory.DIAGNOSTIC,
        "precision": 3,
    },
    "cell_voltage_min": {
        "name": "Lowest Cell Voltage",
        "unit": "V",
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:align-vertical-bottom",
        "category": EntityCategory.DIAGNOSTIC,
        "precision": 3,
    },
    "cell_voltage_diff": {
        "name": "Cell Voltage Delta",
        "unit": "V",
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:format-align-middle",
        "category": EntityCategory.DIAGNOSTIC,
        "precision": 3,
    },
    "cell_voltage_max_index": {
        "name": "Highest Cell",
        "unit": None,
        "device_class": None,
        "state_class": None,
        "icon": "mdi:numeric",
        "category": EntityCategory.DIAGNOSTIC,
    },
    "cell_voltage_min_index": {
        "name": "Lowest Cell",
        "unit": None,
        "device_class": None,
        "state_class": None,
        "icon": "mdi:numeric",
        "category": EntityCategory.DIAGNOSTIC,
    },
    "mos_temperature": {
        "name": "MOS Temperature",
        "unit": "°C",
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:thermometer",
        "category": None,
        "precision": 1,
    },
    "balance_current": {
        "name": "Balance Current",
        "unit": "A",
        "device_class": SensorDeviceClass.CURRENT,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:scale-balance",
        "category": EntityCategory.DIAGNOSTIC,
    },
    "energy_charged": {
        "name": "Energy Charged",
        "unit": "kWh",
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "icon": "mdi:battery-positive",
        "category": None,
        "precision": 3,
    },
    "energy_discharged": {
        "name": "Energy Discharged",
        "unit": "kWh",
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "icon": "mdi:battery-negative",
        "category": None,
        "precision": 3,
    },
}

# Current limits are BMS configuration. JK reads them from the setup frame.
# Pace, RS485 and TDT read them with D9H/DBH. The entity stays unavailable
# until a value arrives.
CURRENT_LIMIT_SENSORS = {
    "charge_current_limit": {
        "name": "Charge Current Limit",
        "key": "view_charge_current_limit",
        "unit": "A",
        "device_class": SensorDeviceClass.CURRENT,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:current-dc",
        "category": EntityCategory.CONFIG,
        "precision": 1,
    },
    "discharge_current_limit": {
        "name": "Discharge Current Limit",
        "key": "view_discharge_current_limit",
        "unit": "A",
        "device_class": SensorDeviceClass.CURRENT,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:current-dc",
        "category": EntityCategory.CONFIG,
        "precision": 1,
    },
}

PACE_CONFIG_SENSORS = {
    "charge_current_alarm": {
        "name": "Charge Current Alarm",
        "key": "view_charge_current_alarm",
        "unit": "A",
        "device_class": SensorDeviceClass.CURRENT,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:current-dc",
        "category": EntityCategory.CONFIG,
        "precision": 1,
    },
    "discharge_current_alarm": {
        "name": "Discharge Current Alarm",
        "key": "view_discharge_current_alarm",
        "unit": "A",
        "device_class": SensorDeviceClass.CURRENT,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:current-dc",
        "category": EntityCategory.CONFIG,
        "precision": 1,
    },
    "limiter_gear": {
        "name": "Charge Limiter Gear",
        "key": None,
        "unit": None,
        "device_class": None,
        "state_class": None,
        "icon": "mdi:speedometer",
        "category": EntityCategory.CONFIG,
    },
}

# JK setup frame: these are configured limits, not live measurements.
JK_CONFIG_SENSORS = {
    "cell_ovp": {
        "name": "Cell Overvoltage Protection",
        "key": "view_vol_cell_ovp",
        "unit": "V",
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:battery-alert",
        "category": EntityCategory.CONFIG,
    },
    "cell_uvp": {
        "name": "Cell Undervoltage Protection",
        "key": "view_vol_cell_uvp",
        "unit": "V",
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:battery-alert",
        "category": EntityCategory.CONFIG,
    },
    "float_charge_voltage": {
        "name": "Float Charge Voltage",
        "key": "view_vol_float_charge",
        "unit": "V",
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:battery-charging",
        "category": EntityCategory.CONFIG,
    },
    "max_charge_voltage": {
        "name": "Inverter Max Charge Voltage",
        "key": "view_vol_inverter_max_charge",
        "unit": "V",
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:battery-charging-high",
        "category": EntityCategory.CONFIG,
    },
}

PACE_COUNTER_SENSORS = {
    "cumulative_charge_ah": {
        "name": "Cumulative Charge",
        "key": "view_cumulative_charge_ah",
        "unit": "Ah",
        "device_class": None,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "icon": "mdi:battery-plus",
        "category": EntityCategory.DIAGNOSTIC,
    },
    "cumulative_discharge_ah": {
        "name": "Cumulative Discharge",
        "key": "view_cumulative_discharge_ah",
        "unit": "Ah",
        "device_class": None,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "icon": "mdi:battery-minus",
        "category": EntityCategory.DIAGNOSTIC,
    },
}

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    """Set up the sensor platform from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    initial_entities = []

    # 1. Register Overall Battery Bank Sensors
    overall_sensors = [
        # key, name, unit, device_class, state_class, icon, category, precision
        ("packs_count", "Packs Count", "packs", None, SensorStateClass.MEASUREMENT, "mdi:database", EntityCategory.DIAGNOSTIC, None),
        ("total_full_capacity", "Total Full Capacity", "Ah", None, SensorStateClass.MEASUREMENT, "mdi:battery-high", EntityCategory.DIAGNOSTIC, 2),
        ("total_remain_capacity", "Total Remaining Capacity", "Ah", None, SensorStateClass.MEASUREMENT, "mdi:battery-clock", None, 2),
        ("total_current", "Total Current", "A", SensorDeviceClass.CURRENT, SensorStateClass.MEASUREMENT, "mdi:current-dc", None, 2),
        ("total_soc", "Total SOC", "%", SensorDeviceClass.BATTERY, SensorStateClass.MEASUREMENT, "mdi:battery-70", None, 1),
        ("total_voltage", "Total Voltage", "V", SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT, "mdi:sine-wave", None, 2),
        ("total_power", "Total Power", "W", SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT, "mdi:battery-charging", None, 1),
        ("total_energy_charged", "Total Energy Charged", "kWh", SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING, "mdi:battery-positive", None, 3),
        ("total_energy_discharged", "Total Energy Discharged", "kWh", SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING, "mdi:battery-negative", None, 3),
        ("total_cell_voltage_max", "Max Cell Voltage", "V", SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT, "mdi:align-vertical-top", EntityCategory.DIAGNOSTIC, 3),
        ("total_cell_voltage_min", "Min Cell Voltage", "V", SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT, "mdi:align-vertical-bottom", EntityCategory.DIAGNOSTIC, 3),
        ("total_cell_voltage_diff", "Cell Voltage Delta", "V", SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT, "mdi:format-align-middle", EntityCategory.DIAGNOSTIC, 3),
    ]

    for key, name, unit, dev_class, state_class, icon, category, precision in overall_sensors:
        initial_entities.append(
            GobelBatteryOverallSensor(
                coordinator, key, name, unit, dev_class, state_class, icon, category, precision
            )
        )

    # Track registered pack IDs
    registered_packs = set()

    @callback
    def async_add_pack_sensors():
        """Add sensors for newly discovered packs."""
        data = coordinator.data
        analog_packs = data.get("analog", []) if data else []
        
        # Default to pack 0 if no packs are detected yet so entities are visible
        if not analog_packs and not registered_packs:
            pack_ids_to_add = [0]
        else:
            pack_ids_to_add = [p.get("pack_id", 0) for p in analog_packs if p.get("pack_id", 0) not in registered_packs]

        new_entities = []
        for pack_id in pack_ids_to_add:
            if pack_id in registered_packs:
                continue
                
            pack_data = next((p for p in analog_packs if p.get("pack_id") == pack_id), None)
            num_cells = len((pack_data or {}).get("cell_voltages") or [])

            # Add predefined metrics (SOC, SOH, Voltage, Current, Cycle Count, etc.)
            for metric, meta in SENSOR_METADATA.items():
                # Only JK BMS supports balance current telemetry
                if metric == "balance_current" and coordinator.bms_type != BMS_TYPE_JK_PB:
                    continue
                if metric == "mos_temperature" and coordinator.bms_type != BMS_TYPE_JK_PB:
                    continue
                if metric == "design_capacity" and coordinator.bms_type == BMS_TYPE_JK_PB:
                    continue
                    
                new_entities.append(
                    GobelBatteryPackSensor(
                        coordinator,
                        pack_id,
                        metric,
                        meta["name"],
                        meta["unit"],
                        meta["device_class"],
                        meta["state_class"],
                        meta["icon"],
                        meta["category"],
                        precision=meta.get("precision"),
                    )
                )

            extra = {}
            if coordinator.bms_type == BMS_TYPE_JK_PB:
                extra.update(CURRENT_LIMIT_SENSORS)
                extra.update(JK_CONFIG_SENSORS)
            elif coordinator.bms_type == BMS_TYPE_PACE_LV_WIFI:
                # The battery pushes analog and status frames. It does not answer
                # the configuration commands, so those sensors are not created.
                pass
            else:
                extra.update(_pace_configuration_sensors())
                extra.update(_pace_readonly_sensors())
                extra["limiter_gear"] = PACE_CONFIG_SENSORS["limiter_gear"]
            if coordinator.bms_type in (BMS_TYPE_PACE_LV, BMS_TYPE_PACE_LV_WIFI):
                extra.update(PACE_COUNTER_SENSORS)
            for metric, meta in extra.items():
                if (
                    meta.get("category") == EntityCategory.CONFIG
                    and not coordinator.owns_configuration(pack_id)
                ):
                    continue
                if coordinator.can_write_config and meta.get("category") == EntityCategory.CONFIG and not meta.get("read_only"):
                    continue
                new_entities.append(
                    GobelBatteryPackSensor(
                        coordinator,
                        pack_id,
                        metric,
                        meta["name"],
                        meta["unit"],
                        meta["device_class"],
                        meta["state_class"],
                        meta["icon"],
                        meta["category"],
                        source_key=meta["key"],
                        precision=meta.get("precision"),
                    )
                )

            # Add cell voltage sensors (Cell 01 Voltage ... Cell N Voltage)
            for cell_idx in range(1, num_cells + 1):
                new_entities.append(
                    GobelBatteryCellVoltageSensor(coordinator, pack_id, cell_idx)
                )

            # Add temperature sensors (Temperature 01 ... Temperature N)
            temps = (pack_data or {}).get("temperatures") or []
            for temp_idx, reading in enumerate(temps, start=1):
                if reading is None:
                    continue
                new_entities.append(
                    GobelBatteryTemperatureSensor(coordinator, pack_id, temp_idx)
                )
                
            registered_packs.add(pack_id)

        for pack in analog_packs:
            temps = pack.get("temperatures") or []
            if temps:
                _drop_missing_probes(
                    hass,
                    entry,
                    pack.get("pack_id", 0),
                    "temp_",
                    {index for index, reading in enumerate(temps, start=1) if reading is not None},
                )
            cells = pack.get("cell_voltages") or []
            if cells:
                _drop_missing_probes(
                    hass,
                    entry,
                    pack.get("pack_id", 0),
                    "cell_",
                    set(range(1, len(cells) + 1)),
                )

        if new_entities:
            async_add_entities(new_entities, update_before_add=True)

    # Register initial overall sensors + any initially detected packs
    async_add_entities(initial_entities, update_before_add=True)
    async_add_pack_sensors()
    entry.async_on_unload(coordinator.async_add_listener(async_add_pack_sensors))


def _drop_missing_probes(hass, entry, pack_id, marker, present):
    """Remove a probe entity only when that slot has no sensor fitted."""
    if not present:
        return
    registry = er.async_get(hass)
    prefix = f"{entry.entry_id}_pack_{pack_id}_{marker}"
    for entity in list(er.async_entries_for_config_entry(registry, entry.entry_id)):
        unique_id = entity.unique_id or ""
        if not unique_id.startswith(prefix):
            continue
        number = unique_id[len(prefix):].split("_", 1)[0]
        if number.isdigit() and int(number) not in present:
            registry.async_remove(entity.entity_id)

class GobelBatteryOverallSensor(CoordinatorEntity, SensorEntity):
    """Sensor representing aggregate battery bank metrics."""

    def __init__(self, coordinator, key, name, unit, device_class, state_class, icon, category, precision=None):
        """Initialize overall sensor."""
        super().__init__(coordinator)
        self._key = key
        self._attr_has_entity_name = False
        self._attr_name = f"{coordinator.device_name} {name}"
        self._attr_translation_key = key
        self._attr_translation_placeholders = {"device": coordinator.device_name}
        self._attr_unique_id = f"{coordinator.entry.entry_id}_total_{key}"
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_icon = icon
        self._attr_entity_category = category
        if precision is not None:
            self._attr_suggested_display_precision = precision

    @property
    def device_info(self):
        """Return device info for overall bank device."""
        return self.coordinator.total_device_info()

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if not super().available:
            return False
        data = self.coordinator.data
        if not data:
            return False
        return len(data.get("analog", [])) > 0

    @property
    def native_value(self):
        """Calculate and return the native value of the aggregate sensor."""
        data = self.coordinator.data
        if not data:
            return None
        analog_packs = data.get("analog", [])
        if not analog_packs:
            return None

        total_packs_num = len(analog_packs)

        if self._key == "packs_count":
            return total_packs_num
        elif self._key == "total_full_capacity":
            return round(sum(d.get("view_full_capacity", 0) for d in analog_packs), 2)
        elif self._key == "total_remain_capacity":
            return round(sum(d.get("view_remain_capacity", 0) for d in analog_packs), 2)
        elif self._key == "total_current":
            return round(sum(d.get("view_current", 0) for d in analog_packs), 2)
        elif self._key == "total_soc":
            total_full = sum(d.get("view_full_capacity", 0) for d in analog_packs)
            total_remain = sum(d.get("view_remain_capacity", 0) for d in analog_packs)
            return round(total_remain / total_full * 100, 1) if total_full > 0 else 0
        elif self._key == "total_voltage":
            return round(sum(d.get("view_voltage", 0) for d in analog_packs) / total_packs_num, 2)
        elif self._key == "total_power":
            return watts_from_kilowatts(sum(d.get("view_power", 0) for d in analog_packs))
        elif self._key == "total_energy_charged":
            return round(sum(d.get("view_energy_charged", 0) or 0 for d in analog_packs), 3)
        elif self._key == "total_energy_discharged":
            return round(sum(d.get("view_energy_discharged", 0) or 0 for d in analog_packs), 3)
        
        # Cell Voltages aggregate
        all_cell_voltages = [v for d in analog_packs for v in d.get("cell_voltages", [])]
        if not all_cell_voltages:
            return None

        if self._key == "total_cell_voltage_max":
            return volts_from_millivolts(max(all_cell_voltages))
        elif self._key == "total_cell_voltage_min":
            return volts_from_millivolts(min(all_cell_voltages))
        elif self._key == "total_cell_voltage_diff":
            return volts_from_millivolts(max(all_cell_voltages) - min(all_cell_voltages))

        return None

class GobelBatteryPackSensor(CoordinatorEntity, SensorEntity):
    """Sensor representing a specific battery pack metric."""

    def __init__(self, coordinator, pack_id, metric, name, unit, device_class, state_class, icon, category, source_key=None, precision=None):
        """Initialize pack sensor."""
        super().__init__(coordinator)
        self.pack_id = pack_id
        self._metric = metric
        self._source_key = source_key
        self._attr_has_entity_name = True
        self._attr_translation_key = metric
        self._attr_unique_id = f"{coordinator.entry.entry_id}_pack_{pack_id}_{metric}"
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_icon = icon
        self._attr_entity_category = category
        if precision is not None:
            self._attr_suggested_display_precision = precision

    @property
    def device_info(self):
        """Return device info for individual pack child device."""
        return self.coordinator.pack_device_info(self.pack_id)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if not super().available:
            return False
        data = self.coordinator.data
        if not data:
            return False
        analog_packs = data.get("analog", [])
        pack_data = next((p for p in analog_packs if p.get("pack_id") == self.pack_id), None)
        if pack_data is None:
            return False
        if self._source_key and self._source_key not in pack_data:
            return False
        return True

    @property
    def native_value(self):
        """Return value of pack metric."""
        data = self.coordinator.data
        if not data:
            return None
        analog_packs = data.get("analog", [])
        
        # Find pack data matching self.pack_id
        pack_data = next((p for p in analog_packs if p.get("pack_id") == self.pack_id), None)
        if not pack_data:
            return None

        if self._metric == "limiter_gear":
            return self.coordinator._limiter_gear.get(self.pack_id)

        if self._source_key:
            return pack_data.get(self._source_key)

        # Map metric keys
        if self._metric == "voltage":
            return pack_data.get("view_voltage")
        elif self._metric == "current":
            return pack_data.get("view_current")
        elif self._metric == "power":
            return watts_from_kilowatts(pack_data.get("view_power"))
        elif self._metric == "soc":
            return pack_data.get("view_SOC")
        elif self._metric == "soh":
            return pack_data.get("view_SOH")
        elif self._metric == "remain_capacity":
            return pack_data.get("view_remain_capacity")
        elif self._metric == "full_capacity":
            return pack_data.get("view_full_capacity")
        elif self._metric == "cycle_number":
            return pack_data.get("view_cycle_number")
        elif self._metric == "design_capacity":
            return pack_data.get("view_design_capacity")
        elif self._metric == "cell_voltage_max":
            return volts_from_millivolts(pack_data.get("cell_voltage_max"))
        elif self._metric == "cell_voltage_min":
            return volts_from_millivolts(pack_data.get("cell_voltage_min"))
        elif self._metric == "cell_voltage_diff":
            return volts_from_millivolts(pack_data.get("cell_voltage_diff"))
        elif self._metric == "cell_voltage_max_index":
            return pack_data.get("cell_voltage_max_index")
        elif self._metric == "cell_voltage_min_index":
            return pack_data.get("cell_voltage_min_index")
        elif self._metric == "mos_temperature":
            return pack_data.get("view_mos_temperature")
        elif self._metric == "balance_current":
            return pack_data.get("view_balance_current")
        elif self._metric == "energy_charged":
            return pack_data.get("view_energy_charged")
        elif self._metric == "energy_discharged":
            return pack_data.get("view_energy_discharged")

        return None

    @property
    def extra_state_attributes(self):
        """Alarm threshold that belongs to a configured current limit."""
        alarm_keys = {
            "charge_current_limit": "view_charge_current_alarm",
            "discharge_current_limit": "view_discharge_current_alarm",
        }
        alarm_key = alarm_keys.get(self._metric)
        if alarm_key is None:
            return None
        data = self.coordinator.data
        if not data:
            return None
        pack_data = next(
            (p for p in data.get("analog", []) if p.get("pack_id") == self.pack_id),
            None,
        )
        if not pack_data or pack_data.get(alarm_key) is None:
            return None
        return {"alarm_threshold_a": pack_data.get(alarm_key)}

class GobelBatteryCellVoltageSensor(CoordinatorEntity, SensorEntity):
    """Sensor representing voltage of a single cell inside a battery pack."""

    def __init__(self, coordinator, pack_id, cell_index):
        """Initialize cell voltage sensor."""
        super().__init__(coordinator)
        self.pack_id = pack_id
        self.cell_index = cell_index
        self._attr_has_entity_name = True
        self._attr_translation_key = "cell_voltage"
        self._attr_translation_placeholders = {"index": f"{cell_index:02d}"}
        self._attr_unique_id = f"{coordinator.entry.entry_id}_pack_{pack_id}_cell_{cell_index}_voltage"
        self._attr_native_unit_of_measurement = "V"
        self._attr_device_class = SensorDeviceClass.VOLTAGE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_suggested_display_precision = 3
        self._attr_icon = "mdi:sine-wave"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def device_info(self):
        """Return device info for individual pack child device."""
        return self.coordinator.pack_device_info(self.pack_id)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if not super().available:
            return False
        data = self.coordinator.data
        if not data:
            return False
        analog_packs = data.get("analog", [])
        return any(p.get("pack_id") == self.pack_id for p in analog_packs)

    @property
    def native_value(self):
        """Return cell voltage."""
        data = self.coordinator.data
        if not data:
            return None
        analog_packs = data.get("analog", [])
        
        pack_data = next((p for p in analog_packs if p.get("pack_id") == self.pack_id), None)
        if not pack_data:
            return None

        voltages = pack_data.get("cell_voltages", [])
        if self.cell_index - 1 < len(voltages):
            return volts_from_millivolts(voltages[self.cell_index - 1])

        return None

class GobelBatteryTemperatureSensor(CoordinatorEntity, SensorEntity):
    """Sensor representing temperature of a single probe inside a battery pack."""

    def __init__(self, coordinator, pack_id, temp_index):
        """Initialize temperature sensor."""
        super().__init__(coordinator)
        self.pack_id = pack_id
        self.temp_index = temp_index
        self._attr_has_entity_name = True
        self._attr_translation_key = "temperature"
        self._attr_translation_placeholders = {"index": f"{temp_index:02d}"}
        self._attr_unique_id = f"{coordinator.entry.entry_id}_pack_{pack_id}_temp_{temp_index}"
        self._attr_native_unit_of_measurement = "°C"
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:thermometer"
        self._attr_entity_category = None

    @property
    def device_info(self):
        """Return device info for individual pack child device."""
        return self.coordinator.pack_device_info(self.pack_id)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        if not super().available:
            return False
        data = self.coordinator.data
        if not data:
            return False
        analog_packs = data.get("analog", [])
        return any(p.get("pack_id") == self.pack_id for p in analog_packs)

    @property
    def native_value(self):
        """Return temperature."""
        data = self.coordinator.data
        if not data:
            return None
        analog_packs = data.get("analog", [])
        
        pack_data = next((p for p in analog_packs if p.get("pack_id") == self.pack_id), None)
        if not pack_data:
            return None

        temps = pack_data.get("temperatures", [])
        if self.temp_index - 1 < len(temps):
            return temps[self.temp_index - 1]

        return None
