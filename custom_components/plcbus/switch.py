"""Support for plcbus switches."""
import logging
from datetime import timedelta

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchEntity
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers.event import track_time_interval

from .lib.plcbus_lib import PLCBUSAPI, PLCBUSException, get_plcbus_interface

_LOGGER = logging.getLogger(__name__)

DOMAIN = "plcbus"

CONF_USER_CODE = "user_code"
CONF_DEVICE = "device"
CONF_UNIT = "unit"

SCAN_INTERVAL = timedelta(seconds=60)


def _normalize_user_code(value):
    """Validate and normalize a two-digit hexadecimal PLCBUS user code."""
    if len(value) != 2 or any(char not in "0123456789abcdefABCDEF" for char in value):
        raise vol.Invalid("user_code must contain exactly two hexadecimal digits")
    return value.upper()


def _normalize_unit_code(value):
    """Validate and normalize a PLCBUS house and unit address."""
    value = value.upper()
    if len(value) < 2 or value[0] not in "ABCDEFGHIJKLMNOP":
        raise vol.Invalid("unit must be a house code A-P followed by a unit 1-16")
    unit_value = value[1:]
    if not unit_value.isascii() or not unit_value.isdigit():
        raise vol.Invalid("unit must be a house code A-P followed by a unit 1-16")
    unit = int(unit_value)
    if not 1 <= unit <= 16:
        raise vol.Invalid("unit must be a house code A-P followed by a unit 1-16")
    return "%s%d" % (value[0], unit)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USER_CODE): vol.All(cv.string, _normalize_user_code),
        vol.Optional(CONF_DEVICE): cv.string,
        vol.Optional(CONF_UNIT, default=[]): vol.All(
            cv.ensure_list_csv, [vol.All(cv.string, _normalize_unit_code)]
        ),
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up PLCBUS switches from YAML."""
    _LOGGER.info("Setting up plcbus devices")

    device_name = config.get(CONF_DEVICE) or get_plcbus_interface()
    if not device_name:
        _LOGGER.error(
            "No PLCBUS serial device found. Set switch.plcbus.device "
            "(for example /dev/ttyUSB0)"
        )
        return False

    previous_data = hass.data.get(DOMAIN, {})
    cancel_poll = previous_data.get("cancel_poll")
    if cancel_poll is not None:
        cancel_poll()
    previous = previous_data.get("api")
    if previous is not None:
        _LOGGER.info("Stopping previous PLCBUS serial handler before reload")
        previous.stop()

    hass.data[DOMAIN] = {
        "api": None,
        "switches": [],
        "houses": set(),
        "cancel_poll": None,
    }
    switches = hass.data[DOMAIN]["switches"]
    houses = hass.data[DOMAIN]["houses"]
    user_code = config.get(CONF_USER_CODE)
    devices = config.get(CONF_UNIT) or []

    def _known_units():
        return {entity.unit_code for entity in switches}

    def commandCB(message):
        _LOGGER.debug("commandCB")
        try:
            command = message["d_command"]
            house = message["d_home_unit"][0]
        except (KeyError, TypeError, IndexError):
            _LOGGER.debug("Ignoring malformed PLCBUS message: %s", message)
            return

        if command == "GET_ALL_ID_PULSE":
            device_found = []
            _LOGGER.debug("get all id pulse response %s", message)
            houses.add(house)
            for i in range(0, 8):
                if message["d_data2"] >> i & 1:
                    unit_code = house + str(i + 1)
                    _LOGGER.info("Find a device with unit_code %s", unit_code)
                    if unit_code not in _known_units():
                        device_found.append(
                            PlcbusSwitch(
                                Api, unit_code, user_code, "mdi:electric-switch", switches
                            )
                        )
            for i in range(0, 8):
                if message["d_data1"] >> i & 1:
                    unit_code = house + str(i + 9)
                    _LOGGER.info("Find a device with unit_code %s", unit_code)
                    if unit_code not in _known_units():
                        device_found.append(
                            PlcbusSwitch(
                                Api, unit_code, user_code, "mdi:electric-switch", switches
                            )
                        )
            if device_found:
                hass.add_job(add_entities, device_found, True)
        elif command == "GET_ALL_ON_ID_PULSE":
            _LOGGER.debug("get all on id pulse response %s", message)
            _apply_on_pulse(switches, house, message["d_data2"], 1)
            _apply_on_pulse(switches, house, message["d_data1"], 9)
        else:
            _LOGGER.debug("receive %s, for unit %s", command, message["d_home_unit"])
            for entity in switches:
                if entity.unit_code != message["d_home_unit"]:
                    continue
                _LOGGER.debug("Device exists %s", entity.name)
                if command in ("STATUS_ON", "ON"):
                    entity.set_state(True)
                elif command in ("STATUS_OFF", "OFF"):
                    entity.set_state(False)

    def messageCB(_message):
        _LOGGER.debug("messageCB")

    try:
        Api = PLCBUSAPI(logging, device_name, commandCB, messageCB)
    except (PLCBUSException, OSError) as err:
        _LOGGER.error("Failed to start PLCBUS on %s: %s", device_name, err)
        return False

    hass.data[DOMAIN]["api"] = Api

    entities = []
    for device in devices:
        _LOGGER.info("device= %s", device)
        houses.add(device[0].upper())
        entities.append(
            PlcbusSwitch(Api, device, user_code, "mdi:electric-switch", switches)
        )
    add_entities(entities, True)

    for unit_code in map(chr, range(ord("A"), ord("K") + 1)):
        _LOGGER.debug("GET_ALL_ID_PULSE unit_code= %s", unit_code)
        Api.send("GET_ALL_ID_PULSE", unit_code, user_code)

    def _poll_on_ids(_now=None):
        poll_houses = houses or {device[0].upper() for device in devices if device}
        for house in list(poll_houses):
            Api.send("GET_ALL_ON_ID_PULSE", house, user_code)

    cancel_poll = track_time_interval(hass, _poll_on_ids, SCAN_INTERVAL)
    hass.data[DOMAIN]["cancel_poll"] = cancel_poll

    def _shutdown(_event=None):
        cancel_poll()
        Api.stop()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, _shutdown)
    return True


def _apply_on_pulse(switches, house, bits, start_unit):
    """Update switch state for an 8-bit ON pulse (units start_unit..start_unit+7)."""
    for i in range(0, 8):
        unit_code = house + str(start_unit + i)
        is_on = bool(bits >> i & 1)
        if is_on:
            _LOGGER.info(
                "Find device that is on with unit_code %s", unit_code
            )
        for entity in switches:
            if entity.unit_code == unit_code:
                entity.set_state(is_on)


class PlcbusSwitch(SwitchEntity):
    """Representation of a Plcbus switch."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, plcbus_API, unit_code, user_code, icon, registry) -> None:
        """Initialize the PLCBUS switch."""
        self._unit_code = unit_code.upper()
        self._user_code = user_code.upper()
        self._name = "PlcbusSwitch_" + self._user_code + "_" + self._unit_code
        self._state = False
        self._plcbus_API = plcbus_API
        self._icon = icon
        self._unique_id = self._name
        registry.append(self)
        _LOGGER.debug(
            "Creating switch device= %s with name %s", self._unit_code, self._name
        )

    @property
    def unit_code(self) -> str:
        """Return the PLCBUS house+unit address."""
        return self._unit_code

    @property
    def name(self) -> str:
        """Return the name of the switch."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this switch."""
        return f"{self._unique_id}"

    @property
    def icon(self) -> str:
        """Return the mdi icon of the entity."""
        return self._icon

    @property
    def is_on(self):
        """If the switch is currently on or off."""
        _LOGGER.debug(
            "switch STATE device= %s with name %s state %s",
            self._unit_code,
            self._name,
            self._state,
        )
        return self._state

    def set_state(self, state):
        """Update local state from the bus and refresh Home Assistant."""
        self._state = state
        _LOGGER.debug(
            "switch set_state device= %s with name %s state %s",
            self._unit_code,
            self._name,
            self._state,
        )
        if self.hass is not None:
            self.schedule_update_ha_state()

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        self._plcbus_API.send("ON", self._unit_code, self._user_code)
        _LOGGER.debug(
            "switch ON command queued for device= %s with name %s",
            self._unit_code,
            self._name,
        )

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        self._plcbus_API.send("OFF", self._unit_code, self._user_code)
        _LOGGER.debug(
            "switch OFF command queued for device= %s with name %s",
            self._unit_code,
            self._name,
        )
