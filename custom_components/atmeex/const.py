"""Constants for the Atmeex Airnanny integration."""

DOMAIN = "atmeex"
CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_PHONE = "phone"
CONF_PHONE_CODE = "phone_code"
CONF_AUTH_METHOD = "auth_method"

AUTH_METHOD_EMAIL = "email"
AUTH_METHOD_PHONE = "phone"

API_BASE_URL = "https://api.iot.atmeex.com"

# Device condition field names
COND_PWR_ON = "pwr_on"
COND_FAN_SPEED = "fan_speed"
COND_CO2_PPM = "co2_ppm"
COND_TEMP_ROOM = "temp_room"
COND_TEMP_IN = "temp_in"
COND_HUM_ROOM = "hum_room"
COND_DAMP_POS = "damp_pos"
COND_COOL_MODE = "cool_mode"
COND_NO_WATER = "no_water"
COND_HUM_STG = "hum_stg"
COND_FIRMWARE_VERSION = "firmware_version"
COND_NETWORK_NAME = "network_name"
COND_TIME = "time"

# Device param field names (control)
PARAM_PWR_ON = "u_pwr_on"
PARAM_FAN_SPEED = "u_fan_speed"
PARAM_DAMP_POS = "u_damp_pos"
PARAM_HUM_STG = "u_hum_stg"
PARAM_TEMP_ROOM = "u_temp_room"
PARAM_AUTO = "u_auto"
PARAM_NIGHT = "u_night"
PARAM_COOL_MODE = "u_cool_mode"
PARAM_NIGHT_START = "u_night_start"
PARAM_NIGHT_STOP = "u_night_stop"
PARAM_TIME_ZONE = "u_time_zone"

# Scan interval
DEFAULT_SCAN_INTERVAL = 30