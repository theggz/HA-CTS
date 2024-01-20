"""HTTP client used to contact the cts API."""
import datetime
from http import HTTPStatus
import logging

from dateutil import parser
import requests
from requests.auth import HTTPBasicAuth

from homeassistant import exceptions
import homeassistant.util.dt as dt_util

from .const import (
    RESOURCE_GENERAL_MESSAGE,
    RESOURCE_STOP_MONITORING,
    RESOURCE_STOPPOINTS_DISCOVERY,
)

_LOGGER = logging.getLogger(__name__)


def due_in_minutes(timestamp: datetime.datetime):
    """Get the time in minutes from a timestamp."""
    diff = timestamp - dt_util.now()

    return str(int(diff.total_seconds() / 60))


class InfoMessageContent:
    """Describes the content of a message."""

    def __init__(self, title: str, period: str, value: str) -> None:
        """Initialize the message content."""
        self._title = title
        self._period = period
        self._value = value

    @property
    def title(self) -> str:
        """Returns the message title."""
        return self._title

    @property
    def period(self) -> str:
        """Returns the message period."""
        return self._period

    @property
    def value(self) -> str:
        """Returns the message text value."""
        return self._value


class InfoMessage:
    """Describes a message."""

    def __init__(
        self,
        itemIdentifier: str,
        messageIdentifier: str,
        channelRef: str,
        impactStart: datetime.datetime,
        impactEnd: datetime.datetime,
        impactedLinesRefs: list[str],
        priority: str,
        message: InfoMessageContent,
    ) -> None:
        """Initialize the message."""
        self._item_identifier = itemIdentifier
        self._message_identifier = messageIdentifier
        self._channel_ref = channelRef
        self._impact_start = impactStart
        self._impact_end = impactEnd
        self._impacted_lines_refs = impactedLinesRefs
        self._priority = priority
        self._message = message

    @property
    def item_identifier(self) -> str:
        """Returns the item identifier."""
        return self._item_identifier

    @property
    def message_identifier(self) -> str:
        """Returns the message identifier."""
        return self._message_identifier

    @property
    def channel_ref(self) -> str:
        """Returns the channel reference."""
        return self._channel_ref

    @property
    def impact_start(self) -> datetime.datetime:
        """Returns the impact start."""
        return self._impact_start

    @property
    def impact_end(self) -> datetime.datetime:
        """Returns the impact end."""
        return self._impact_end

    @property
    def impacted_lines_refs(self) -> list[str]:
        """Returns the impacted lines references."""
        return self._impacted_lines_refs

    @property
    def priority(self) -> str:
        """Returns the message priority."""
        return self._priority

    @property
    def message(self) -> InfoMessageContent:
        """Returns the message content."""
        return self._message


class Coordinates:
    """Describes coordinates."""

    def __init__(self, longitude, latitude) -> None:
        """Initialize the coordinates."""
        self._longitude = longitude
        self._latitude = latitude

    @property
    def longitude(self) -> float:
        """Returns coordinates longitude."""
        return self._longitude

    @property
    def latitude(self) -> float:
        """Returns the coordinates latitude."""
        return self._latitude


class CtsStopPoint:
    """Describes a stop point."""

    def __init__(
        self,
        ref: str,
        coordinates: Coordinates,
        name: str,
        code: str,
        logicalCode: str,
        isFlexhop: bool,
    ) -> None:
        """Initialize the data object."""
        self._ref = ref
        self._coordinates = coordinates
        self._name = name
        self._code = code
        self._logical_code = logicalCode
        self._is_flexhop = isFlexhop

    @property
    def ref(self) -> str:
        """Returns the stop point reference."""
        return self._ref

    @property
    def coordinates(self) -> Coordinates:
        """Returns the stop point coordinates."""
        return self._coordinates

    @property
    def name(self) -> str:
        """Returns the stop point name."""
        return self._name

    @property
    def code(self) -> str:
        """Returns the stop point code."""
        return self._code

    @property
    def logical_code(self) -> str:
        """Returns the stop point logical code."""
        return self._logical_code

    @property
    def is_flexhop(self) -> bool:
        """Returns the stop point flexhop state."""
        return self._is_flexhop


class CtsStopPointVisit:
    """Describes a stop point visit."""

    def __init__(
        self,
        monitoringRefParam: str,
        validUntil: datetime.datetime,
        stopCode: str,
        lineRef: str,
        vehicleMode: str,
        lineName: str,
        destinationName: str,
        stopPointName: str,
        departureTime: datetime.datetime,
        realTime: bool,
    ) -> None:
        """Initialize the data object."""
        self._monitoring_ref_param = monitoringRefParam
        self._valid_until = validUntil
        self._stop_code = stopCode
        self._line_ref = lineRef
        self._vehicle_mode = vehicleMode
        self._line_name = lineName
        self._destination_name = destinationName
        self._stop_point_name = stopPointName
        self._departure_time = departureTime
        self._real_time = realTime

    @property
    def monitoring_ref_param(self) -> str:
        """Returns the stop point visit monitoring ref input param."""
        return self._monitoring_ref_param

    @property
    def valid_until(self) -> datetime.date:
        """Returns the stop point visit data validity."""
        return self._valid_until

    @property
    def stop_code(self) -> str:
        """Returns the stop point code."""
        return self._stop_code

    @property
    def line_ref(self) -> str:
        """Returns the stop point line reference."""
        return self._line_ref

    @property
    def vehicle_mode(self) -> str:
        """Returns the stop point vehicle mode (bus / tram / ...)."""
        return self._vehicle_mode

    @property
    def line_name(self) -> str:
        """Returns the stop point line name."""
        return self._line_name

    @property
    def destination_name(self) -> str:
        """Returns the stop point destination name."""
        return self._destination_name

    @property
    def stop_point_name(self) -> str:
        """Returns the stop point name."""
        return self._stop_point_name

    @property
    def departure_time(self) -> datetime.datetime:
        """Returns the stop point visit departure time."""
        return self._departure_time

    @property
    def real_time(self) -> bool:
        """Returns the stop point visit real time state."""
        return self._real_time

    def get_minutes_to_departure_time(self) -> str:
        """Return the minutes remaining until the departure."""
        return due_in_minutes(self.departure_time)


class CtsClient:
    """The Class handling the data retrieval."""

    def __init__(self, token) -> None:
        """Initialize the data object."""
        self.token = token

    def get_general_messages(self) -> list[InfoMessage]:
        """Test the connection."""
        basic = HTTPBasicAuth(self.token, "")
        params = {}
        _LOGGER.debug("Getting general information messages")
        response = requests.get(
            RESOURCE_GENERAL_MESSAGE, params, auth=basic, timeout=10
        )
        if response.status_code != HTTPStatus.OK:
            if response.status_code == HTTPStatus.UNAUTHORIZED:
                raise InvalidToken
            if response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR:
                _LOGGER.error(
                    "Cannot connect to CTS api due to a technical error : %s",
                    response.reason,
                )
                raise CannotConnect

        _LOGGER.debug("Parsing results")
        json_result = response.json()
        result_list = json_result["ServiceDelivery"]["GeneralMessageDelivery"][
            "InfoMessage"
        ]

        info_message_list: list[InfoMessage] = []

        for message in result_list:
            info_message_content = InfoMessageContent(
                title=next(
                    msg["MessageText"][0]["Value"]
                    for msg in message["Content"]["Message"]
                    if msg["MessageZoneRef"] == "title"
                ),
                period=next(
                    msg["MessageText"][0]["Value"]
                    for msg in message["Content"]["Message"]
                    if msg["MessageZoneRef"] == "period"
                ),
                value=next(
                    msg["MessageText"][0]["Value"]
                    for msg in message["Content"]["Message"]
                    if msg["MessageZoneRef"] == "details"
                ),
            )

            info_message = InfoMessage(
                itemIdentifier=message["ItemIdentifier"],
                messageIdentifier=message["InfoMessageIdentifier"],
                channelRef=message["InfoChannelRef"],
                impactStart=parser.parse(message["Content"]["ImpactStartDateTime"]),
                impactEnd=parser.parse(message["Content"]["ImpactEndDateTime"]),
                impactedLinesRefs=message["Content"]["ImpactedLineRef"],
                priority=message["Content"]["Priority"],
                message=info_message_content,
            )

            info_message_list.append(info_message)

        return info_message_list

    def discover_stoppoints(self) -> list[CtsStopPoint]:
        """Discover all stop points."""
        basic = HTTPBasicAuth(self.token, "")
        params = {}
        _LOGGER.debug("Discovering stop points")
        response = requests.get(
            RESOURCE_STOPPOINTS_DISCOVERY, params, auth=basic, timeout=10
        )
        if response.status_code != HTTPStatus.OK:
            if response.status_code == HTTPStatus.UNAUTHORIZED:
                raise InvalidToken
            if response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR:
                _LOGGER.error(
                    "Cannot connect to CTS api due to a technical error : %s",
                    response.reason,
                )
                raise CannotConnect

        json_result = response.json()
        result_list = json_result["StopPointsDelivery"]["AnnotatedStopPointRef"]
        stop_points: list[CtsStopPoint] = []

        for stop_point in result_list:
            cts_stop_point = CtsStopPoint(
                ref=stop_point["StopPointRef"],
                coordinates=Coordinates(
                    stop_point["Location"]["Longitude"],
                    stop_point["Location"]["Latitude"],
                ),
                name=stop_point["StopName"],
                code=stop_point["Extension"]["StopCode"],
                logicalCode=stop_point["Extension"]["LogicalStopCode"],
                isFlexhop=stop_point["Extension"]["IsFlexhopStop"],
            )
            stop_points.append(cts_stop_point)

        return sorted(stop_points, key=lambda x: x.name)

    def monitor_stop(
        self, stopCode: str, lineRef: str | None = None
    ) -> list[CtsStopPointVisit]:
        """Get the latest data from the cts api."""
        basic = HTTPBasicAuth(self.token, "")
        params = {}
        params["monitoringRef"] = stopCode
        if lineRef is not None:
            params["lineRef"] = lineRef

        _LOGGER.debug("Getting stop data with params : %s", params)
        response = requests.get(
            RESOURCE_STOP_MONITORING, params, auth=basic, timeout=10
        )

        if response.status_code != HTTPStatus.OK:
            if response.status_code == HTTPStatus.UNAUTHORIZED:
                raise InvalidToken
            if response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR:
                _LOGGER.error(
                    "Cannot connect to CTS api due to a technical error : %s",
                    response.reason,
                )
                raise CannotConnect

        result = response.json()
        response_delivery = result["ServiceDelivery"]["StopMonitoringDelivery"][0]

        valid_until = response_delivery["ValidUntil"]
        monitoring_ref = response_delivery["MonitoringRef"]
        visits = response_delivery.get("MonitoredStopVisit") or []

        visit_data_list: list[CtsStopPointVisit] = []

        for visit in visits:
            vehicle = visit.get("MonitoredVehicleJourney")
            visit_data = CtsStopPointVisit(
                monitoringRefParam=monitoring_ref,
                validUntil=valid_until,
                stopCode=visit["StopCode"],
                lineRef=vehicle["LineRef"],
                vehicleMode=vehicle["VehicleMode"],
                lineName=vehicle["PublishedLineName"],
                destinationName=vehicle["DestinationName"],
                stopPointName=vehicle["MonitoredCall"]["StopPointName"],
                departureTime=parser.parse(
                    vehicle["MonitoredCall"]["ExpectedDepartureTime"]
                ),
                realTime=vehicle["MonitoredCall"]["Extension"]["IsRealTime"],
            )
            visit_data_list.append(visit_data)

        if len(visit_data_list) <= 0:
            _LOGGER.warning(
                "The stop monitor call (params: %s) did not return any data", params
            )

        return visit_data_list


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidToken(exceptions.HomeAssistantError):
    """Error to indicate auth failed due to invalid api token."""


class AlreadyConfigured(exceptions.HomeAssistantError):
    """Error to indicate CTS API Key is already configured."""
