"""Constanten voor de Windows Shutdown-integratie."""

DOMAIN = "windows_shutdown"

# Options
CONF_API_KEY = "api_key"
CONF_DELAY = "delay"
CONF_SHUTDOWN_TYPE = "shutdown_type"

DEFAULT_DELAY = 60
DEFAULT_SHUTDOWN_TYPE = "shutdown"
SHUTDOWN_TYPES: tuple[str, ...] = ("shutdown", "restart", "logoff")

# Zeroconf service-type (moet overeenkomen met de client)
SERVICE_TYPE = "_ha-shutdown._tcp.local."

# Standaard-waarden
DEFAULT_PORT = 8765
DEFAULT_TIMEOUT = 5        # seconden per HTTP-verzoek
POLL_INTERVAL = 30         # seconden tussen status-polls

# Apparaat-info
DEVICE_MANUFACTURER = "Microsoft"
DEVICE_MODEL = "Windows PC"
