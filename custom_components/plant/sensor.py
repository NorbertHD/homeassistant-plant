"""Dummy sensors for monitoring plants."""
from datetime import datetime, timedelta
import logging
import random

import voluptuous as vol

from homeassistant.components.recorder import history
from homeassistant.components.sensor import (
    ENTITY_ID_FORMAT,
    PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_NAME,
    ATTR_TEMPERATURE,
    ATTR_UNIT_OF_MEASUREMENT,
    CONDUCTIVITY,
    CONF_NAME,
    CONF_SENSORS,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_ILLUMINANCE,
    DEVICE_CLASS_TEMPERATURE,
    LIGHT_LUX,
    PERCENTAGE,
    STATE_OK,
    STATE_PROBLEM,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import (
    Entity,
    EntityCategory,
    async_generate_entity_id,
)
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util import dt as dt_util, slugify

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "plant"

READING_BATTERY = "battery"
READING_TEMPERATURE = ATTR_TEMPERATURE
READING_MOISTURE = "moisture"
READING_CONDUCTIVITY = "conductivity"
READING_BRIGHTNESS = "brightness"

ATTR_PROBLEM = "problem"
ATTR_SENSORS = "sensors"
PROBLEM_NONE = "none"
ATTR_MAX_BRIGHTNESS_HISTORY = "max_brightness"
ATTR_SPECIES = "species"
ATTR_LIMITS = "limits"
ATTR_IMAGE = "image"

# we're not returning only one value, we're returning a dict here. So we need
# to have a separate literal for it to avoid confusion.
ATTR_DICT_OF_UNITS_OF_MEASUREMENT = "unit_of_measurement_dict"

CONF_MIN_BATTERY_LEVEL = f"min_{READING_BATTERY}"
CONF_MIN_TEMPERATURE = f"min_{READING_TEMPERATURE}"
CONF_MAX_TEMPERATURE = f"max_{READING_TEMPERATURE}"
CONF_MIN_MOISTURE = f"min_{READING_MOISTURE}"
CONF_MAX_MOISTURE = f"max_{READING_MOISTURE}"
CONF_MIN_CONDUCTIVITY = f"min_{READING_CONDUCTIVITY}"
CONF_MAX_CONDUCTIVITY = f"max_{READING_CONDUCTIVITY}"
CONF_MIN_BRIGHTNESS = f"min_{READING_BRIGHTNESS}"
CONF_MAX_BRIGHTNESS = f"max_{READING_BRIGHTNESS}"
CONF_CHECK_DAYS = "check_days"
CONF_SPECIES = "species"
CONF_IMAGE = "image"

CONF_PLANTBOOK = "openplantbook"
CONF_PLANTBOOK_CLIENT = "client_id"
CONF_PLANTBOOK_SECRET = "secret"


CONF_SENSOR_BATTERY_LEVEL = READING_BATTERY
CONF_SENSOR_MOISTURE = READING_MOISTURE
CONF_SENSOR_CONDUCTIVITY = READING_CONDUCTIVITY
CONF_SENSOR_TEMPERATURE = READING_TEMPERATURE
CONF_SENSOR_BRIGHTNESS = READING_BRIGHTNESS

CONF_WARN_BRIGHTNESS = "warn_low_brightness"

DEFAULT_MIN_BATTERY_LEVEL = 20
DEFAULT_MIN_TEMPERATURE = 10
DEFAULT_MAX_TEMPERATURE = 40
DEFAULT_MIN_MOISTURE = 20
DEFAULT_MAX_MOISTURE = 60
DEFAULT_MIN_CONDUCTIVITY = 500
DEFAULT_MAX_CONDUCTIVITY = 3000
DEFAULT_MIN_BRIGHTNESS = 0
DEFAULT_MAX_BRIGHTNESS = 100000
DEFAULT_CHECK_DAYS = 3


# Flag for enabling/disabling the loading of the history from the database.
# This feature is turned off right now as its tests are not 100% stable.
ENABLE_LOAD_HISTORY = False


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    """Set up OpenPlantBook from a config entry."""
    _LOGGER.info(entry.data)
    # plant = hass.data[DOMAIN][entry.entry_id]
    sensor_entities = [
        PlantDummyMoisture(hass, entry),
        PlantDummyTemperature(hass, entry),
        PlantDummyBrightness(hass, entry),
        PlantDummyConductivity(hass, entry),
        PlantDummyHumidity(hass, entry),
    ]
    async_add_entities(sensor_entities)
    return True


class PlantDummyStatus(SensorEntity):
    def __init__(self, hass, config):
        """Initialize the Plant component."""
        self._config = config
        self._default_state = STATE_UNKNOWN
        # self._plant = plantdevice
        self.entity_id = async_generate_entity_id(
            f"{DOMAIN}.{{}}", self.name, current_ids={}
        )
        if not self._attr_native_value or self._attr_native_value == STATE_UNKNOWN:
            self._attr_native_value = self._default_state


class PlantDummyBrightness(PlantDummyStatus):
    def __init__(self, hass, config):
        self._attr_name = f"{config.data['plant_info']['plant_name']} Dummy Brightness"
        self._attr_unique_id = f"{config.entry_id}-dummy-brightness"
        self._attr_icon = "mdi:brightness-6"
        self._attr_native_unit_of_measurement = LIGHT_LUX
        super().__init__(hass, config)

    async def async_update(self):
        self._attr_native_value = random.randint(0, 100) * 1000

    @property
    def device_class(self):
        return DEVICE_CLASS_ILLUMINANCE


class PlantDummyConductivity(PlantDummyStatus):
    def __init__(self, hass, config):
        self._attr_name = (
            f"{config.data['plant_info']['plant_name']} Dummy Conductivity"
        )
        self._attr_unique_id = f"{config.entry_id}-dummy-conductivity"
        self._attr_icon = "mdi:spa-outline"
        self._attr_native_unit_of_measurement = "uS/cm"
        super().__init__(hass, config)

    async def async_update(self):
        self._attr_native_value = random.randint(40, 200) * 10


class PlantDummyMoisture(PlantDummyStatus):
    def __init__(self, hass, config):
        self._attr_name = (
            f"{config.data['plant_info']['plant_name']} Dummy Moisture Level"
        )
        self._attr_unique_id = f"{config.entry_id}-dummy-moisture"
        self._attr_icon = "mdi:water"
        self._attr_native_unit_of_measurement = PERCENTAGE

        super().__init__(hass, config)

    async def async_update(self):
        self._attr_native_value = random.randint(0, 80)

    @property
    def device_class(self):
        return DEVICE_CLASS_HUMIDITY


class PlantDummyTemperature(PlantDummyStatus):
    def __init__(self, hass, config):
        self._attr_name = f"{config.data['plant_info']['plant_name']} Dummy Temperature"
        self._attr_unique_id = f"{config.entry_id}-dummy-temperature"
        self._attr_icon = "mdi:thermometer"
        self._attr_native_unit_of_measurement = TEMP_CELSIUS

        super().__init__(hass, config)

    async def async_update(self):
        r = random.randint(15, 20)
        # _LOGGER.info("Getting curret temperature: %s", r)
        self._attr_native_value = r

    @property
    def device_class(self):
        return DEVICE_CLASS_TEMPERATURE


class PlantDummyHumidity(PlantDummyStatus):
    def __init__(self, hass, config):
        self._attr_name = f"{config.data['plant_info']['plant_name']} Dummy Humidity"
        self._attr_unique_id = f"{config.entry_id}-dummy-humidity"
        self._attr_icon = "mdi:water-percent"
        self._attr_native_unit_of_measurement = PERCENTAGE
        super().__init__(hass, config)

    async def async_update(self):
        r = random.randint(20, 90)
        # _LOGGER.info("Getting curret temperature: %s", r)
        self._attr_native_value = r

    @property
    def device_class(self):
        return DEVICE_CLASS_HUMIDITY
