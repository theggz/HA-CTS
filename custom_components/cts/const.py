"""Constants for the cts integration."""

DOMAIN = "cts"
DEVICE_MANUFACTURER = "cts-strasbourg"

RESOURCE_BASE_URL = "https://api.cts-strasbourg.eu/v1/siri/2.0"
RESOURCE_GENERAL_MESSAGE = RESOURCE_BASE_URL + "/general-message"
RESOURCE_LINES_DISCOVERY = RESOURCE_BASE_URL + "/lines-discovery"
RESOURCE_STOPPOINTS_DISCOVERY = RESOURCE_BASE_URL + "/stoppoints-discovery"
RESOURCE_STOP_MONITORING = RESOURCE_BASE_URL + "/stop-monitoring"

DEFAULT_SCAN_INTERVAL = 5
MIN_SCAN_INTERVAL = 1

CONF_API_TOKEN = "api_token"
CONF_LOGICAL_STOP_CODE = "logical_stop_code"
CONF_STOP_CODE = "stop_code"
CONF_STOP_NAME = "stop_name"
CONF_LINE_REF = "line_ref"
CONF_MONITORED_STOPS = "monitored_stops"
