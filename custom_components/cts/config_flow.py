"""Config flow for cts integration."""
import logging
from operator import itemgetter
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import (
    DeviceEntry,
    async_entries_for_config_entry,
    async_get,
)
from homeassistant.helpers.selector import (
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_API_TOKEN,
    CONF_LINE_REF,
    CONF_LOGICAL_STOP_CODE,
    CONF_MONITORED_STOPS,
    CONF_STOP_CODE,
    CONF_STOP_NAME,
    DOMAIN,
)
from .cts_client import CannotConnect, CtsClient, CtsStopPoint, InvalidToken

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_TOKEN): cv.string,
    }
)

# TODO : permettre setup des arrêts directement dans le config flow


class CTSConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """CTS config flow."""

    # The schema version of the entries that it creates
    # Home Assistant will call your migrate method if the version changes
    VERSION = 1

    _available_stop_points: list[CtsStopPoint] = []
    data: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial user step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_API_TOKEN])
            self._abort_if_unique_id_configured()
            client = CtsClient(user_input[CONF_API_TOKEN])

            try:
                self._available_stop_points = await self.hass.async_add_executor_job(
                    client.discover_stoppoints
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidToken:
                errors["base"] = "invalid_api_token"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if not errors:
                    self.data = user_input
                    return await self.async_step_menu(user_input=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_menu(self, user_input: dict[str, Any]) -> FlowResult:
        """Allow to create an entity, or finish the configuration."""
        return self.async_show_menu(step_id="menu", menu_options=["add_stop", "finish"])

    async def async_step_finish(self, user_input: dict[str, Any]) -> FlowResult:
        """Finishes the configuration and create the cts entry."""
        return self.async_create_entry(
            title="CTS", data=self.data, description="CTS stops monitoring"
        )

    async def async_step_add_stop(self, user_input: dict[str, Any]) -> FlowResult:
        """Allow to create a new stop sensor."""
        return self.async_create_entry(
            title="CTS", data=self.data, description="CTS stops monitoring"
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlowManager:
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlowManager, config_entries.OptionsFlow):
    """Handle the option flow for cts integration."""

    data: dict[str, Any] = {}

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        super().__init__(hass=self.hass)
        self.config_entry = config_entry
        self._cts_client = CtsClient(config_entry.data.get(CONF_API_TOKEN))
        self.data = config_entry.data.copy()
        self.data[CONF_MONITORED_STOPS] = []

        monitored_stops = config_entry.options.get(CONF_MONITORED_STOPS)
        if monitored_stops:
            for stop in monitored_stops:
                self.data[CONF_MONITORED_STOPS].append(
                    {
                        CONF_LINE_REF: stop[CONF_LINE_REF],
                        CONF_STOP_CODE: stop[CONF_STOP_CODE],
                    }
                )

        self._available_stop_points: list[CtsStopPoint] = []
        self._stop_point_data_schema = None
        self._destination_data_schema = None
        self._configured_entries_schema = None

        self._current_stop = {}

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the user choice."""

        entity_registry = async_get(self.hass)
        entries = async_entries_for_config_entry(
            entity_registry, self.config_entry.entry_id
        )

        if len(entries) <= 0:
            return await self._async_handle_step(
                flow=self, step_id="add_stop", user_input=None
            )

        return self.async_show_menu(
            step_id="init",
            menu_options=["add_stop", "remove_stop"],
        )

    async def async_step_add_stop(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the stop point configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._current_stop[CONF_LOGICAL_STOP_CODE] = user_input[
                CONF_LOGICAL_STOP_CODE
            ]
            return await self._async_handle_step(
                flow=self, step_id="set_destination", user_input=None
            )

        # Load the stop points in the selector via API call
        try:
            self._available_stop_points = await self.hass.async_add_executor_job(
                self._cts_client.discover_stoppoints
            )
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidToken:
            errors["base"] = "invalid_api_token"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            if not errors:
                stop_points_options: dict[str, str] = {}
                for item in self._available_stop_points:
                    stop_points_options[item.logical_code] = item.name

                self._stop_point_data_schema = vol.Schema(
                    {
                        vol.Required(CONF_LOGICAL_STOP_CODE): SelectSelector(
                            SelectSelectorConfig(
                                options=[
                                    SelectOptionDict(value=k, label=v)
                                    for k, v in stop_points_options.items()
                                ],
                                mode=SelectSelectorMode.DROPDOWN,
                            ),
                        ),
                    }
                )

        return self.async_show_form(
            step_id="add_stop",
            data_schema=self._stop_point_data_schema,
            errors=errors,
        )

    async def async_step_set_destination(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the stop destination configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            stop_code_data = str(user_input.get(CONF_STOP_CODE))
            self._current_stop[CONF_LINE_REF] = stop_code_data.split("_", maxsplit=1)[0]
            self._current_stop[CONF_STOP_CODE] = stop_code_data.split("_")[1]

            if any(
                x[CONF_LINE_REF] == self._current_stop[CONF_LINE_REF]
                and x[CONF_STOP_CODE] == self._current_stop[CONF_STOP_CODE]
                for x in self.data[CONF_MONITORED_STOPS]
            ):
                _LOGGER.info("Stop %s is already configured", stop_code_data)
            else:
                self.data[CONF_MONITORED_STOPS].append(self._current_stop)

            return self.async_create_entry(
                title="",
                data=self.data,
            )

        try:
            destinations = await self.hass.async_add_executor_job(
                self._cts_client.monitor_stop,
                self._current_stop[CONF_LOGICAL_STOP_CODE],
            )
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidToken:
            errors["base"] = "invalid_api_token"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            if not errors:
                self._current_stop[CONF_STOP_NAME] = destinations[0].stop_point_name

                destinations_options: dict[str, str] = {}
                for item in sorted(destinations, key=lambda x: x.line_name):
                    destinations_options[
                        f"{item.line_ref}_{item.stop_code}"
                    ] = f"({item.line_ref}) {item.destination_name}"

                self._destination_data_schema = vol.Schema(
                    {
                        vol.Required(CONF_STOP_CODE): SelectSelector(
                            SelectSelectorConfig(
                                options=[
                                    SelectOptionDict(value=k, label=v)
                                    for k, v in destinations_options.items()
                                ],
                                mode=SelectSelectorMode.DROPDOWN,
                            ),
                        ),
                    }
                )

        return self.async_show_form(
            step_id="set_destination",
            data_schema=self._destination_data_schema,
            errors=errors,
        )

    async def async_step_remove_stop(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the stop point configuration."""
        entity_registry = async_get(self.hass)
        entries = async_entries_for_config_entry(
            entity_registry, self.config_entry.entry_id
        )

        if user_input is not None:
            for entry_id in user_input["entries_to_remove"]:
                removed_device_identifiers = [
                    list(x.identifiers)[0][1] for x in entries if x.id == entry_id
                ][0].split("_", 1)

                stop_to_remove = [
                    x
                    for x in self.data[CONF_MONITORED_STOPS]
                    if x[CONF_LINE_REF] == removed_device_identifiers[0]
                    and x[CONF_STOP_CODE] == removed_device_identifiers[1]
                ][0]

                self.data[CONF_MONITORED_STOPS].remove(stop_to_remove)

                entity_registry.async_remove_device(entry_id)

            return self.async_create_entry(title="", data=self.data)

        # Populating multi-select.
        self._configured_entries_schema = vol.Schema(
            {
                vol.Required("entries_to_remove"): SelectSelector(
                    SelectSelectorConfig(
                        options=[
                            SelectOptionDict(
                                value=device_entry.dict_repr["id"],
                                label=device_entry.dict_repr["name"],
                            )
                            for device_entry in entries
                        ],
                        mode=SelectSelectorMode.LIST,
                        multiple=True,
                    ),
                ),
            }
        )

        return self.async_show_form(
            step_id="remove_stop", data_schema=self._configured_entries_schema
        )
