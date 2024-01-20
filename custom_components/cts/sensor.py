"""Support for Strasbourg transport company real time information from api.cts-strasbourg.eu.

For more info on the API see :
https://www.cts-strasbourg.eu/fr/portail-open-data/
"""
from __future__ import annotations

from contextlib import suppress
from datetime import timedelta
import logging

from config.custom_components.cts.cts_client import CtsClient
from homeassistant.components.sensor import ENTITY_ID_FORMAT, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import generate_entity_id
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_API_TOKEN,
    CONF_LINE_REF,
    CONF_MONITORED_STOPS,
    CONF_STOP_CODE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

DEVICE_ID = "stop_monitor"
DATA_PROVIDER = "api.cts-strasbourg.eu"

ATTR_NAME = "name"
ATTR_VEHICLE_TYPE = "vehicle_type"
ATTR_LINE = "line"
ATTR_DESTINATION = "destination"
ATTR_STOP_CODE = "stop_code"
ATTR_STOP_NAME = "stop_name"
ATTR_DUE_IN = "due_in"
ATTR_DUE_AT = "due_at"
ATTR_NEXT_UP = "next_in"
ATTR_REALTIME = "real_time"

SCAN_INTERVAL = timedelta(minutes=1)
TIME_STR_FORMAT = "%H:%M"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    """Setups sensors from a config entry created in the integrations UI."""

    _LOGGER.debug("Setting up CTS entry, entry=%s", entry)

    config = hass.data[DOMAIN][entry.entry_id]

    cts_client = CtsClient(config[CONF_API_TOKEN])

    stops = entry.options.get(CONF_MONITORED_STOPS)

    if stops is None or len(stops) == 0:
        _LOGGER.info("No stop options specified, skipping entry setting")
        return

    _LOGGER.info("Adding %s cts sensors", len(stops))

    sensors = []
    for stop in stops:
        sensors.append(
            NextDepartureSensor(
                hass,
                cts_client,
                stop[CONF_LINE_REF],
                stop[CONF_STOP_CODE],
            )
        )

    async_add_entities(sensors, update_before_add=True)


class NextDepartureSensor(SensorEntity):
    """Implementation of a 'next departure' sensor."""

    _attr_attribution = "Data provided by " + DATA_PROVIDER
    _attr_has_entity_name = True
    _attr_icon = "mdi:train-bus"
    _name = "next departure"
    _direction = ""

    def __init__(
        self, hass: HomeAssistant, ctsClient: CtsClient, lineRef: str, stopCode: str
    ) -> None:
        """Initialize the sensor."""
        super().__init__()
        self.entity_id = generate_entity_id(
            ENTITY_ID_FORMAT, f"next_{lineRef}_{stopCode}", hass=hass
        )
        self._cts_api = ctsClient
        self._line_ref = lineRef
        self._stop_code = stopCode
        self._device_name = ""
        self._times = self._state = None
        self._available = False

    @property
    def unique_id(self) -> str:
        """Return the entity unique id."""
        return f"{self._line_ref}_{self._stop_code}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        identifiers: set[tuple[str, str]] = {(DOMAIN, self.unique_id)}
        return DeviceInfo(
            identifiers=identifiers,
            name=self._device_name,
            manufacturer=DATA_PROVIDER,
        )

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if self._times is not None:
            next_up = "None"
            if len(self._times) > 1:
                next_up = self._times[1].get_minutes_to_departure_time()

            return {
                ATTR_VEHICLE_TYPE: self._times[0].vehicle_mode,
                ATTR_LINE: self._times[0].line_name,
                ATTR_DESTINATION: self._times[0].destination_name,
                ATTR_DUE_IN: self._times[0].get_minutes_to_departure_time(),
                ATTR_DUE_AT: self._times[0].departure_time,
                ATTR_STOP_CODE: self._stop_code,
                ATTR_STOP_NAME: self._times[0].stop_point_name,
                ATTR_REALTIME: self._times[0].real_time,
                ATTR_NEXT_UP: next_up,
            }

    @property
    def native_unit_of_measurement(self) -> str:
        """Return the unit this state is expressed in."""
        return UnitOfTime.MINUTES

    async def async_update(self) -> None:
        """Get the latest data from cts api and update the states."""

        _LOGGER.debug(
            "Updating sensor data for stop %s (line %s)",
            self._stop_code,
            self._line_ref,
        )

        stop_point_visits = await self.hass.async_add_executor_job(
            self._cts_api.monitor_stop, self._stop_code, self._line_ref
        )
        self._available = True
        self._times = stop_point_visits
        with suppress(TypeError):
            self._state = self._times[0].get_minutes_to_departure_time()

        self._attr_icon = (
            "mdi:bus" if self._times[0].vehicle_mode == "bus" else "mdi:tram"
        )
        self._device_name = f"({self._times[0].line_ref}) {self._times[0].stop_point_name} - {self._times[0].destination_name}"
