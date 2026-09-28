"""Config flow for Gobel Battery Monitor integration."""
import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

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
    CONF_DEVICE_NAME,
    BMS_TYPES,
    CONNECTION_TYPES,
    BATTERY_PORTS,
    CONN_TYPE_ETHERNET,
    CONN_TYPE_WIFI,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_MAX_PARALLEL,
    DEFAULT_BAUD_RATE,
    DEFAULT_IP_PORT,
    DEFAULT_JK_DISPLAY_INDEX_START,
    DEFAULT_DEVICE_NAME,
    BMS_TYPE_PACE_LV,
    BMS_TYPE_PACE_LV_WIFI,
)

from .pace_probe import ACTIVE, PASSIVE, probe_pace_tcp

_LOGGER = logging.getLogger(__name__)


def _is_network(connection_type: str) -> bool:
    return connection_type in (CONN_TYPE_ETHERNET, CONN_TYPE_WIFI)


def _dropdown(options, translation_key):
    return SelectSelector(
        SelectSelectorConfig(
            options=options,
            translation_key=translation_key,
            mode=SelectSelectorMode.DROPDOWN,
        )
    )


class GobelBatteryConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Gobel Battery."""

    VERSION = 1

    def __init__(self) -> None:
        self._reconfigure = False
        self.config_data: dict = {}

    async def async_step_user(self, user_input=None):
        """Handle the initial setup step."""
        return await self._async_common_step(user_input, step_id="user")

    async def async_step_reconfigure(self, user_input=None):
        """Allow changing an existing config entry from the UI."""
        self._reconfigure = True
        entry = self._get_reconfigure_entry()
        self.config_data = dict(entry.data)
        return await self._async_common_step(user_input, step_id="reconfigure")

    async def _async_common_step(self, user_input, step_id: str):
        """Shared first step for setup and reconfigure."""
        errors = {}
        defaults = self.config_data if self._reconfigure else {}

        if user_input is not None:
            self.config_data = {**defaults, **user_input}
            if _is_network(user_input[CONF_CONNECTION_TYPE]):
                return await self.async_step_network()
            return await self.async_step_serial()

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_DEVICE_NAME,
                    default=defaults.get(CONF_DEVICE_NAME, DEFAULT_DEVICE_NAME),
                ): str,
                vol.Required(
                    CONF_BMS_TYPE, default=defaults.get(CONF_BMS_TYPE, BMS_TYPES[0])
                ): _dropdown(BMS_TYPES, "bms_type"),
                vol.Required(
                    CONF_CONNECTION_TYPE,
                    default=defaults.get(CONF_CONNECTION_TYPE, CONNECTION_TYPES[0]),
                ): _dropdown(CONNECTION_TYPES, "connection_type"),
                vol.Required(
                    CONF_BATTERY_PORT,
                    default=defaults.get(CONF_BATTERY_PORT, BATTERY_PORTS[0]),
                ): _dropdown(BATTERY_PORTS, "battery_port"),
                vol.Optional(
                    CONF_POLL_INTERVAL,
                    default=defaults.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=3600)),
                vol.Optional(
                    CONF_MAX_PARALLEL,
                    default=defaults.get(CONF_MAX_PARALLEL, DEFAULT_MAX_PARALLEL),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=32)),
                vol.Optional(
                    CONF_JK_DISPLAY_INDEX_START,
                    default=defaults.get(
                        CONF_JK_DISPLAY_INDEX_START, DEFAULT_JK_DISPLAY_INDEX_START
                    ),
                ): vol.In(["00", "01"]),
            }
        )

        return self.async_show_form(
            step_id=step_id, data_schema=data_schema, errors=errors
        )

    async def async_step_network(self, user_input=None):
        """Handle network configuration parameters (IP and port)."""
        errors = {}
        defaults = self.config_data

        if user_input is not None:
            user_data = self._connection_data(user_input, network=True)
            if user_data[CONF_BMS_TYPE] in (BMS_TYPE_PACE_LV, BMS_TYPE_PACE_LV_WIFI):
                self._pending_entry = user_data
                try:
                    self._probe_result = await self.hass.async_add_executor_job(
                        probe_pace_tcp,
                        user_data[CONF_IP_ADDRESS],
                        user_data[CONF_IP_PORT],
                    )
                except OSError as err:
                    _LOGGER.debug("Pace probe failed: %s", err)
                    self._probe_result = "unreachable"
                if self._probe_result == ACTIVE:
                    self._pending_entry[CONF_BMS_TYPE] = BMS_TYPE_PACE_LV
                elif self._probe_result == PASSIVE:
                    self._pending_entry[CONF_BMS_TYPE] = BMS_TYPE_PACE_LV_WIFI
                return await self.async_step_probe()
            return self._create_from_data(user_data)

        network_schema = vol.Schema(
            {
                vol.Required(
                    CONF_IP_ADDRESS, default=defaults.get(CONF_IP_ADDRESS, "")
                ): str,
                vol.Required(
                    CONF_IP_PORT, default=defaults.get(CONF_IP_PORT, DEFAULT_IP_PORT)
                ): int,
            }
        )

        return self.async_show_form(
            step_id="network", data_schema=network_schema, errors=errors
        )

    async def async_step_probe(self, user_input=None):
        """Show which Pace mode the dongle answered with, then save it."""
        if user_input is not None:
            return await self._create_from_data(self._pending_entry)
        return self.async_show_form(
            step_id="probe",
            data_schema=vol.Schema({}),
            description_placeholders={"result": self._probe_result},
        )

    async def _create_from_data(self, user_data):
        unique_id = f"{user_data[CONF_IP_ADDRESS]}_{user_data[CONF_IP_PORT]}"
        await self.async_set_unique_id(unique_id)
        if self._reconfigure:
            self._abort_if_unique_id_configured()
            return self.async_update_reload_and_abort(
                self._get_reconfigure_entry(),
                title=user_data[CONF_DEVICE_NAME],
                data=user_data,
                options={},
                unique_id=unique_id,
            )
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title=user_data[CONF_DEVICE_NAME], data=user_data)

    async def async_step_serial(self, user_input=None):
        """Handle serial configuration parameters (Port and Baud rate)."""
        errors = {}
        defaults = self.config_data

        if user_input is not None:
            user_data = self._connection_data(user_input, network=False)
            unique_id = user_data[CONF_USB_PORT]
            await self.async_set_unique_id(unique_id)
            if self._reconfigure:
                self._abort_if_unique_id_configured()
                return self.async_update_reload_and_abort(
                    self._get_reconfigure_entry(),
                    title=user_data[CONF_DEVICE_NAME],
                    data=user_data,
                    options={},
                    unique_id=unique_id,
                )
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=user_data[CONF_DEVICE_NAME], data=user_data
            )

        serial_schema = vol.Schema(
            {
                vol.Required(
                    CONF_USB_PORT, default=defaults.get(CONF_USB_PORT, "/dev/ttyUSB0")
                ): str,
                vol.Required(
                    CONF_BAUD_RATE, default=defaults.get(CONF_BAUD_RATE, DEFAULT_BAUD_RATE)
                ): int,
            }
        )

        return self.async_show_form(
            step_id="serial", data_schema=serial_schema, errors=errors
        )

    def _connection_data(self, user_input: dict, network: bool) -> dict:
        """Build a clean config dict so a switched connection type drops stale keys."""
        data = {
            CONF_DEVICE_NAME: self.config_data[CONF_DEVICE_NAME],
            CONF_BMS_TYPE: self.config_data[CONF_BMS_TYPE],
            CONF_CONNECTION_TYPE: self.config_data[CONF_CONNECTION_TYPE],
            CONF_BATTERY_PORT: self.config_data[CONF_BATTERY_PORT],
            CONF_POLL_INTERVAL: self.config_data.get(
                CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL
            ),
            CONF_MAX_PARALLEL: self.config_data.get(
                CONF_MAX_PARALLEL, DEFAULT_MAX_PARALLEL
            ),
            CONF_JK_DISPLAY_INDEX_START: self.config_data.get(
                CONF_JK_DISPLAY_INDEX_START, DEFAULT_JK_DISPLAY_INDEX_START
            ),
        }
        data.update(user_input)
        if network:
            data.pop(CONF_USB_PORT, None)
            data.pop(CONF_BAUD_RATE, None)
        else:
            data.pop(CONF_IP_ADDRESS, None)
            data.pop(CONF_IP_PORT, None)
        return data

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Expose poll interval and pack options without removing the device."""
        return GobelBatteryOptionsFlow()


class GobelBatteryOptionsFlow(config_entries.OptionsFlow):
    """Edit runtime options. Connection settings use the reconfigure flow."""

    async def async_step_init(self, user_input=None):
        """Edit values that should apply on the next reload."""
        entry = self.config_entry
        current = {**entry.data, **entry.options}

        if user_input is not None:
            turning_on = bool(user_input.get(CONF_EXPERT_CONFIG)) and not current.get(
                CONF_EXPERT_CONFIG
            )
            if turning_on:
                self._pending_options = user_input
                return await self.async_step_expert_warning()
            return self.async_create_entry(title="", data=user_input)

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_POLL_INTERVAL,
                    default=current.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=3600)),
                vol.Optional(
                    CONF_MAX_PARALLEL,
                    default=current.get(CONF_MAX_PARALLEL, DEFAULT_MAX_PARALLEL),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=32)),
                vol.Optional(
                    CONF_JK_DISPLAY_INDEX_START,
                    default=current.get(
                        CONF_JK_DISPLAY_INDEX_START, DEFAULT_JK_DISPLAY_INDEX_START
                    ),
                ): vol.In(["00", "01"]),
                vol.Optional(
                    CONF_EXPERT_CONFIG,
                    default=bool(current.get(CONF_EXPERT_CONFIG, False)),
                ): bool,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema, errors={})

    async def async_step_expert_warning(self, user_input=None):
        """Require an explicit confirmation before settings become writable."""
        if user_input is not None:
            if not user_input.get("confirm_expert"):
                return self.async_show_form(
                    step_id="expert_warning",
                    data_schema=self._expert_warning_schema(),
                    errors={"base": "expert_not_confirmed"},
                )
            return self.async_create_entry(title="", data=self._pending_options)
        return self.async_show_form(
            step_id="expert_warning",
            data_schema=self._expert_warning_schema(),
            errors={},
        )

    @staticmethod
    def _expert_warning_schema():
        return vol.Schema({vol.Required("confirm_expert", default=False): bool})
