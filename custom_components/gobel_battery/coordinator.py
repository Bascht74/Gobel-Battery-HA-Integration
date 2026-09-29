"""DataUpdateCoordinator for the Gobel Battery Monitor integration."""
import logging
import asyncio
import time
import threading
from datetime import timedelta
import async_timeout

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.storage import Store
from homeassistant.core import HomeAssistant

from .const import (
    DOMAIN,
    CONF_BMS_TYPE,
    CONF_CONNECTION_TYPE,
    CONF_BATTERY_PORT,
    CONF_IP_ADDRESS,
    CONF_IP_PORT,
    CONF_USB_PORT,
    CONF_BAUD_RATE,
    CONF_POLL_INTERVAL,
    CONF_JK_DISPLAY_INDEX_START,
    CONF_MAX_PARALLEL,
    CONF_EXPERT_CONFIG,
    BMS_TYPE_PACE_LV,
    BMS_TYPE_PACE_LV_WIFI,
    BMS_TYPE_JK_PB,
    BMS_TYPE_TDT,
)

from .bms_comm import BMSCommunication
from .pace_limits import LIMIT_POLL_SECONDS
from .pace_config import (
    FIELD_BY_KEY,
    GROUP_BY_NAME,
    GROUPS,
    decode_group,
    read_configuration_slice,
    read_group,
    write_configuration_field,
)
from .pace_identity import pack_owns_configuration, read_identity
from .pace_write import write_buzzer, write_clock, write_led, write_limiter, write_limiter_gear, write_mosfet
from .measurements import bms_throughput_kwh, integrate_energy_kwh, watts_from_kilowatts
from .pacebms_rs232 import PACEBMS232
from .pacebms_rs485 import PACEBMS485
from .pacebms_wifi import PACEBMSWIFI
from .jkbms_rs485 import JKBMS485
from .tdtbms_rs232 import TDTBMS232

_LOGGER = logging.getLogger(__name__)

class DummyHAComm:
    """Mock class to satisfy driver dependencies on HA_MQTT without publishing."""
    def __init__(self, *args, **kwargs):
        pass
    def publish_sensor_state(self, *args, **kwargs):
        pass
    def publish_sensor_discovery(self, *args, **kwargs):
        pass
    def publish_warn_state(self, *args, **kwargs):
        pass
    def publish_warn_discovery(self, *args, **kwargs):
        pass
    def publish_binary_sensor_state(self, *args, **kwargs):
        pass
    def publish_binary_sensor_discovery(self, *args, **kwargs):
        pass
    def connect(self, *args, **kwargs):
        return True

class GobelBatteryUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Gobel BMS battery data."""

    def __init__(self, hass: HomeAssistant, entry) -> None:
        """Initialize the coordinator."""
        self.entry = entry
        merged = {**entry.data, **entry.options}
        self.device_name = merged.get("device_name", "Gobel Battery")
        self.bms_type = merged.get(CONF_BMS_TYPE)
        self.connection_type = merged.get(CONF_CONNECTION_TYPE)
        self.battery_port = merged.get(CONF_BATTERY_PORT)
        self.ip_address = merged.get(CONF_IP_ADDRESS)
        self.ip_port = merged.get(CONF_IP_PORT)
        self.usb_port = merged.get(CONF_USB_PORT)
        self.baud_rate = merged.get(CONF_BAUD_RATE)
        self.max_parallel = merged.get(CONF_MAX_PARALLEL, 16)
        self.jk_display_index_start = merged.get(CONF_JK_DISPLAY_INDEX_START, "01")

        poll_interval = merged.get(CONF_POLL_INTERVAL, 5)
        super().__init__(
            hass,
            _LOGGER,
            name=f"Gobel Battery {self.device_name}",
            update_interval=timedelta(seconds=poll_interval),
        )

        self.bms_comm = None
        self.bms = None
        self.dummy_ha = DummyHAComm()

        self.pack_cache = {}
        self.pack_failures = {}
        self.max_failures = 3
        self._energy = {}
        self._energy_ts = None
        self._limit_cache = {}
        self._config_cache = {}
        self._identity = {}
        self._limiter_gear = {}
        self._last_reopen = 0
        self._bus_lock = threading.Lock()
        self._store = Store(hass, 1, f"{DOMAIN}.energy.{entry.entry_id}")

    def _setup_bms_sync(self):
        """Synchronous setup of the BMS communication and driver."""
        _LOGGER.info("Initializing BMS connection for: %s", self.device_name)
        self.bms_comm = BMSCommunication(
            interface=self.connection_type,
            serial_port=self.usb_port,
            baud_rate=self.baud_rate,
            ethernet_ip=self.ip_address,
            ethernet_port=self.ip_port,
            buffer_size=1024,
            debug=0
        )
        if not self.bms_comm.connect():
            raise Exception("Failed to connect to BMS communication port")

        # Initialize specific protocol class
        if self.bms_type == BMS_TYPE_PACE_LV:
            if self.battery_port == "rs232":
                self.bms = PACEBMS232(
                    bms_comm=self.bms_comm,
                    ha_comm=self.dummy_ha,
                    bms_type=self.bms_type,
                    data_refresh_interval=self.update_interval.total_seconds(),
                    debug=0,
                    if_random=0
                )
            elif self.battery_port == "rs485":
                self.bms = PACEBMS485(
                    bms_comm=self.bms_comm,
                    ha_comm=self.dummy_ha,
                    data_refresh_interval=self.update_interval.total_seconds(),
                    debug=0,
                    if_random=0
                )
        elif self.bms_type == BMS_TYPE_PACE_LV_WIFI:
            self.bms = PACEBMSWIFI(
                bms_comm=self.bms_comm,
                ha_comm=self.dummy_ha,
                bms_type=self.bms_type,
                data_refresh_interval=self.update_interval.total_seconds(),
                debug=0,
                if_random=0
            )
        elif self.bms_type == BMS_TYPE_JK_PB:
            jk_pack_index_start = 0 if self.jk_display_index_start in ["0", "00"] else 1
            self.bms = JKBMS485(
                bms_comm=self.bms_comm,
                ha_comm=self.dummy_ha,
                bms_type=self.bms_type,
                data_refresh_interval=self.update_interval.total_seconds(),
                debug=0,
                if_random=0,
                ha_comm_jk=None,
                pack_index_start=jk_pack_index_start
            )
        elif self.bms_type == BMS_TYPE_TDT:
            self.bms = TDTBMS232(
                bms_comm=self.bms_comm,
                ha_comm=self.dummy_ha,
                data_refresh_interval=self.update_interval.total_seconds(),
                debug=0,
                if_random=0
            )
        else:
            raise Exception(f"Unsupported BMS type: {self.bms_type}")

    async def async_setup(self):
        """Set up the connection and restore energy counters."""
        stored = await self._store.async_load()
        if stored and isinstance(stored.get("packs"), dict):
            self._energy = stored["packs"]
        try:
            await self.hass.async_add_executor_job(self._setup_bms_sync)
            return True
        except Exception as err:
            _LOGGER.error("Failed to set up BMS coordinator for %s: %s", self.device_name, err)
            return False

    @property
    def expert_config(self):
        """True when the user enabled writable BMS configuration."""
        return bool(self.entry.options.get(CONF_EXPERT_CONFIG, False))

    def owns_configuration(self, pack_id):
        """True when a write to this pack reaches its own BMS."""
        return pack_owns_configuration(self.battery_port, pack_id)

    @property
    def can_write_config(self):
        """Expert mode only replaces sensors when this protocol can be written."""
        return self.expert_config and self.bms_type not in (BMS_TYPE_JK_PB, BMS_TYPE_PACE_LV_WIFI)

    def _fetch_data_sync(self):
        """Fetch data, waiting if an expert write is using the bus."""
        if not self._bus_lock.acquire(timeout=20):
            raise UpdateFailed("BMS bus is busy")
        try:
            return self._fetch_data_inner()
        finally:
            self._bus_lock.release()

    def _fetch_data_inner(self):
        """Synchronous update call running inside thread executor."""
        if not self.bms:
            raise UpdateFailed("BMS driver is not set up")

        # Determine pack indices to query
        pack_list = []
        if self.bms_type == BMS_TYPE_PACE_LV and self.battery_port == "rs485":
            for pack_number in range(0, self.max_parallel + 1):
                try:
                    result = self.bms.get_pack_num_data(pack_number)
                    if result == pack_number:
                        pack_list.append(pack_number)
                except Exception:
                    pass
            if not pack_list:
                pack_list = [0]
        elif self.bms_type == BMS_TYPE_TDT:
            try:
                pack_quantity = self.bms.get_pack_quantity_data()
                pack_list = list(range(1, pack_quantity + 1))
            except Exception:
                pack_list = [1]
        else:
            pack_list = [None]

        analog_data = []
        warning_data = []

        if self.bms_type == BMS_TYPE_JK_PB:
            # JK BMS reads frame caches populated by its background listener thread
            analog_data = self.bms.get_analog_data()
            warning_data = self.bms.get_warning_data()
        else:
            for p in pack_list:
                try:
                    analog_pack = self.bms.get_analog_data(p)
                    warning_pack = self.bms.get_warning_data(p)
                    p_id = p if p is not None else 0
                    if analog_pack:
                        if isinstance(analog_pack, list):
                            for idx, item in enumerate(analog_pack):
                                if "pack_id" not in item:
                                    item["pack_id"] = item.get("pack_index", idx)
                            analog_data.extend(analog_pack)
                        else:
                            if "pack_id" not in analog_pack:
                                analog_pack["pack_id"] = analog_pack.get("pack_index", p_id)
                            analog_data.append(analog_pack)
                    if warning_pack:
                        if isinstance(warning_pack, list):
                            for idx, item in enumerate(warning_pack):
                                if "pack_id" not in item:
                                    item["pack_id"] = item.get("pack_index", idx)
                            warning_data.extend(warning_pack)
                        else:
                            if "pack_id" not in warning_pack:
                                warning_pack["pack_id"] = warning_pack.get("pack_index", p_id)
                            warning_data.append(warning_pack)
                except Exception as ex:
                    _LOGGER.error("Error polling pack %s: %s", p, ex)

        # Reconcile with cache to hold old data on occasional read failures
        seen_analog_packs = {item.get("pack_id", i): item for i, item in enumerate(analog_data)}
        seen_warning_packs = {item.get("pack_id", i): item for i, item in enumerate(warning_data)}
        if not seen_analog_packs and self.connection_type != "serial":
            self._reopen_link()
        
        final_analog_data = []
        final_warning_data = []
        
        all_pack_ids = set(seen_analog_packs.keys()) | set(seen_warning_packs.keys()) | set(self.pack_cache.keys())
        
        for p_id in all_pack_ids:
            if p_id in seen_analog_packs:
                # Read successful
                self.pack_failures[p_id] = 0
                if p_id not in self.pack_cache:
                    self.pack_cache[p_id] = {}
                self.pack_cache[p_id]['analog'] = seen_analog_packs[p_id]
                if p_id in seen_warning_packs:
                    self.pack_cache[p_id]['warning'] = seen_warning_packs[p_id]
                
                final_analog_data.append(seen_analog_packs[p_id])
                if p_id in seen_warning_packs:
                    final_warning_data.append(seen_warning_packs[p_id])
            else:
                # Read failed
                self.pack_failures[p_id] = self.pack_failures.get(p_id, 0) + 1
                failures = self.pack_failures[p_id]
                
                if failures <= self.max_failures and p_id in self.pack_cache:
                    _LOGGER.debug("Using cached data for pack %s (failure %s/%s)", p_id, failures, self.max_failures)
                    if 'analog' in self.pack_cache[p_id]:
                        final_analog_data.append(self.pack_cache[p_id]['analog'])
                    if 'warning' in self.pack_cache[p_id]:
                        final_warning_data.append(self.pack_cache[p_id]['warning'])
                else:
                    if failures == self.max_failures + 1:
                        _LOGGER.warning("Pack %s data unavailable after %s consecutive failures", p_id, failures)

        self._attach_current_limits(final_analog_data)
        self._attach_identity(final_analog_data)
        self._apply_energy_totals(final_analog_data)

        return {
            "analog": final_analog_data,
            "warning": final_warning_data,
        }

    def _reopen_link(self):
        """The dongle keeps no session across a reboot or firmware update."""
        if not self.bms_comm:
            return
        now = time.monotonic()
        if now - self._last_reopen < 15:
            return
        self._last_reopen = now
        _LOGGER.warning("No BMS data from %s, reconnecting", self.ip_address)
        try:
            self.bms_comm.reconnect()
        except Exception as err:
            _LOGGER.debug("Reconnect failed: %s", err)

    def _attach_current_limits(self, packs):
        """Read a few Pace/TDT configuration groups per poll. JK limits come from the setup frame."""
        if not packs or not self.bms or not hasattr(self.bms, "generate_bms_request"):
            return
        now = time.monotonic()
        per_pack = self.bms_type != BMS_TYPE_JK_PB and self.battery_port == "rs485"
        targets = [pack.get("pack_id", 0) for pack in packs] if per_pack else [None]
        for target in targets:
            cache_key = "all" if target is None else str(target)
            slot = self._config_cache.setdefault(
                cache_key, {"cursor": 0, "values": {}, "raw": {}, "ts": 0}
            )
            if slot["cursor"] == 0 and slot["values"] and now - slot["ts"] < LIMIT_POLL_SECONDS:
                continue
            try:
                values, raw = read_configuration_slice(self.bms, slot["cursor"], pack_number=target)
            except Exception as err:
                _LOGGER.debug("Configuration read failed: %s", err)
                values, raw = {}, {}
            slot["values"].update(values)
            slot["raw"].update(raw)
            slot["cursor"] = (slot["cursor"] + 4) % len(GROUPS)
            if slot["cursor"] == 0:
                slot["ts"] = now

        for pack in packs:
            if not self.owns_configuration(pack.get("pack_id", 0)):
                continue
            cache_key = str(pack.get("pack_id", 0)) if per_pack else "all"
            values = self._config_cache.get(cache_key, {}).get("values")
            if values:
                pack.update(values)

    def _attach_identity(self, packs):
        """Read firmware, hardware version and serial about once per hour."""
        if (
            not packs
            or not self.bms
            or not hasattr(self.bms, "generate_bms_request")
            or self.bms_type in (BMS_TYPE_JK_PB, BMS_TYPE_PACE_LV_WIFI)
        ):
            return
        now = time.monotonic()
        per_pack = self.battery_port == "rs485"
        for pack in packs:
            pack_id = pack.get("pack_id", 0)
            if not self.owns_configuration(pack_id):
                continue
            slot = self._identity.setdefault(pack_id, {"ts": 0})
            if slot.get("software_version") and now - slot["ts"] < 3600:
                self._copy_identity(pack, slot)
                continue
            try:
                found = read_identity(self.bms, pack_id if per_pack else None)
            except Exception as err:
                _LOGGER.debug("Identity read failed: %s", err)
                found = {}
            if any(found.get(key) for key in ("software_version", "hardware_version", "serial_number")):
                slot.update(found)
                slot["ts"] = now
            self._copy_identity(pack, slot)

    @staticmethod
    def _copy_identity(pack, slot):
        for key in ("software_version", "hardware_version", "serial_number"):
            if slot.get(key):
                pack[key] = slot[key]

    def version_fields(self, pack_id=None):
        """Home Assistant device-registry fields for one pack, or the bank."""
        if pack_id not in (None,) and not self.owns_configuration(pack_id):
            return {}
        slot = {}
        if pack_id is not None:
            slot = self._identity.get(pack_id, {})
        elif self._identity:
            slot = next(iter(self._identity.values()))
        pack = None
        for item in (self.data or {}).get("analog", []):
            if pack_id is None or item.get("pack_id") == pack_id:
                pack = item
                break
        software = slot.get("software_version") or (pack or {}).get("software_version") or ""
        hardware = slot.get("hardware_version") or (pack or {}).get("hardware_version") or ""
        serial = slot.get("serial_number") or (pack or {}).get("serial_number") or ""
        fields = {}
        if software:
            fields["sw_version"] = software
        if hardware:
            fields["hw_version"] = hardware
        if serial:
            fields["serial_number"] = serial
        return fields

    def total_device_info(self):
        info = {
            "identifiers": {(DOMAIN, f"{self.entry.entry_id}_total")},
            "name": f"{self.device_name} (Total)",
            "manufacturer": "Gobel Power",
            "model": f"{self.bms_type} Bank",
        }
        info.update(self.version_fields())
        return info

    def pack_device_info(self, pack_id):
        display = pack_id + (0 if self.jk_display_index_start == "00" else 1)
        info = {
            "identifiers": {(DOMAIN, f"{self.entry.entry_id}_pack_{pack_id}")},
            "name": f"{self.device_name} Pack {display:02d}",
            "via_device": (DOMAIN, f"{self.entry.entry_id}_total"),
            "manufacturer": "Gobel Power",
            "model": self.bms_type,
        }
        info.update(self.version_fields(pack_id))
        return info

    def _apply_energy_totals(self, packs):
        """Publish charged and discharged energy in kWh.

        Pace analog frames carry cumulative amp-hours. Those are converted with
        a fixed 3.2 V per cell, so the value comes from the BMS and survives a
        restart. JK has no lifetime energy counter, so power is integrated and
        the result is stored on disk.
        """
        now = time.monotonic()
        prev = self._energy_ts
        self._energy_ts = now
        elapsed = None if prev is None else now - prev

        for pack in packs:
            pack_id = str(pack.get("pack_id", 0))
            slot = self._energy.setdefault(pack_id, {"charged": 0.0, "discharged": 0.0})
            cell_count = pack.get("view_num_cells") or len(pack.get("cell_voltages") or [])
            design_ah = pack.get("view_design_capacity")
            charged = bms_throughput_kwh(
                pack.get("view_cumulative_charge_ah"),
                pack.get("view_cumulative_discharge_ah"),
                cell_count,
                design_ah,
            )
            discharged = bms_throughput_kwh(
                pack.get("view_cumulative_discharge_ah"),
                pack.get("view_cumulative_charge_ah"),
                cell_count,
                design_ah,
            )
            source = "bms"
            if charged is None or discharged is None:
                source = "integrated"
                power_w = watts_from_kilowatts(pack.get("view_power")) or 0.0
                integrated_charged, integrated_discharged = integrate_energy_kwh(
                    slot.get("charged", 0.0),
                    slot.get("discharged", 0.0),
                    power_w,
                    elapsed,
                )
                if charged is None:
                    charged = integrated_charged
                if discharged is None:
                    discharged = integrated_discharged
            slot["charged"] = round(float(charged), 3)
            slot["discharged"] = round(float(discharged), 3)
            pack["view_energy_charged"] = slot["charged"]
            pack["view_energy_discharged"] = slot["discharged"]
            pack["energy_source"] = source

    async def async_save_energy(self):
        """Persist integrated energy so a reload does not start from zero."""
        await self._store.async_save({"packs": self._energy})

    async def async_apply_expert_change(self, pack_id, kind, value):
        """Write one BMS setting. Caller must only expose this in expert mode."""
        if self.bms_type == BMS_TYPE_JK_PB or not hasattr(self.bms, "generate_bms_request"):
            raise RuntimeError("Dieses BMS unterstützt das Schreiben der Konfiguration nicht.")
        ok = await self.hass.async_add_executor_job(self._apply_expert_change_sync, pack_id, kind, value)
        if not ok:
            raise RuntimeError("Das BMS hat die Änderung nicht bestätigt.")
        await self.async_request_refresh()

    def _apply_expert_change_sync(self, pack_id, kind, value):
        if not self._bus_lock.acquire(timeout=20):
            return False
        try:
            pack = self._analog_pack(pack_id)
            if kind in FIELD_BY_KEY:
                cache_key = str(pack_id) if self.battery_port == "rs485" else "all"
                slot = self._config_cache.setdefault(
                    cache_key, {"cursor": 0, "values": {}, "raw": {}, "ts": 0}
                )
                group = GROUP_BY_NAME[FIELD_BY_KEY[kind]["group"]]
                raw = slot["raw"].get(group["name"])
                if raw is None:
                    raw = read_group(self.bms, group, pack_id)
                if raw is None:
                    return False
                updated = write_configuration_field(self.bms, kind, value, raw, pack_id)
                if updated is None:
                    return False
                slot["raw"][group["name"]] = updated
                decoded = decode_group(group, updated)
                slot["values"].update(decoded)
                pack.update(decoded)
                return True
            if kind == "charge_switch":
                ok = write_mosfet(self.bms, "charge", bool(value), pack_id)
            elif kind == "discharge_switch":
                ok = write_mosfet(self.bms, "discharge", bool(value), pack_id)
            elif kind == "limiter_switch":
                ok = write_limiter(self.bms, bool(value), pack_id)
            elif kind == "buzzer_switch":
                ok = write_buzzer(self.bms, bool(value), pack_id)
            elif kind == "led_switch":
                ok = write_led(self.bms, bool(value), pack_id)
            elif kind == "set_clock":
                ok = write_clock(self.bms, value, pack_id)
                if ok:
                    stamp = f"{value:%Y-%m-%d %H:%M:%S}"
                    for item in (self.data or {}).get("analog", []):
                        if item.get("pack_id") == pack_id:
                            item["view_bms_clock"] = stamp
            elif kind == "limiter_gear":
                ok = write_limiter_gear(self.bms, value, pack_id)
                if ok:
                    self._limiter_gear[pack_id] = value
            else:
                return False
            if ok:
                self._set_switch_flag(pack_id, kind, value)
            return ok
        finally:
            self._bus_lock.release()

    def _analog_pack(self, pack_id):
        for pack in (self.data or {}).get("analog", []):
            if pack.get("pack_id") == pack_id:
                return pack
        return {}

    def _set_switch_flag(self, pack_id, kind, value):
        flags = {
            "charge_switch": ("instruction_state", "status_charge_enabled"),
            "discharge_switch": ("instruction_state", "status_discharge_enabled"),
            "limiter_switch": ("instruction_state", "status_current_limit_enabled"),
            "buzzer_switch": ("control_state", "buzzer_warn_function"),
            "led_switch": ("control_state", "led_warn_function"),
        }
        target = flags.get(kind)
        if target is None:
            return
        section, flag = target
        for pack in (self.data or {}).get("warning", []):
            if pack.get("pack_id") == pack_id:
                pack.setdefault(section, {})[flag] = bool(value)

    async def _async_update_data(self):
        """Fetch data from BMS."""
        # First fetch needs more time for pack discovery (up to 15s wait + processing)
        timeout_seconds = 45 if not getattr(self, '_first_fetch_done', False) else 20
        async with async_timeout.timeout(timeout_seconds):
            try:
                data = await self.hass.async_add_executor_job(self._fetch_data_sync)
                self._first_fetch_done = True
                await self.async_save_energy()
                return data
            except Exception as err:
                raise UpdateFailed(f"BMS communication error: {err}") from err

    def shutdown(self):
        """Release bms sockets and threads."""
        _LOGGER.info("Closing BMS connection for: %s", self.device_name)
        if self.bms and hasattr(self.bms, "stop"):
            try:
                self.bms.stop()
            except Exception as e:
                _LOGGER.error("Error stopping BMS background thread: %s", e)
        if self.bms_comm:
            try:
                self.bms_comm.disconnect()
            except Exception as e:
                _LOGGER.error("Error closing BMS port: %s", e)
