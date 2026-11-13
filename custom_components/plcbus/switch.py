"""Support for plcbus switches."""
import logging
from datetime import timedelta

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchEntity
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.event import async_track_time_interval

from .const import CONF_DEVICE, CONF_UNIT, CONF_USER_CODE, DOMAIN
from .lib.plcbus_lib import PLCBUSAPI, PLCBUSException, get_plcbus_interface
from .validation import normalize_unit_code, normalize_user_code

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=60)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USER_CODE): vol.All(cv.string, normalize_user_code),
        vol.Optional(CONF_DEVICE): cv.string,
        vol.Optional(CONF_UNIT, default=[]): vol.All(
            cv.ensure_list_csv, [vol.All(cv.string, normalize_unit_code)]
        ),
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Import legacy YAML into a configuration entry."""
    hass.add_job(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "import"}, data=dict(config)
        )
    )


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up switches from UI or imported configuration."""
    runtime = {"api": None, "switches": [], "houses": set(), "pending": []}
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = runtime

    def add_entities(entities, update_before_add=False):
        hass.add_job(async_add_entities, entities, update_before_add)

    try:
        await hass.async_add_executor_job(
            _setup_switches, hass, entry.data, add_entities, runtime
        )
    except (PLCBUSException, OSError) as err:
        runtime["stopped"] = True
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if runtime["api"] is not None:
            await hass.async_add_executor_job(runtime["api"].stop)
        raise ConfigEntryNotReady(str(err)) from err

    @callback
    def _poll_on_ids(_now=None):
        if runtime.get("stopped"):
            return
        for house in list(runtime["houses"]):
            runtime["api"].send("GET_ALL_ON_ID_PULSE", house, entry.data[CONF_USER_CODE])

    cancel_poll = async_track_time_interval(hass, _poll_on_ids, SCAN_INTERVAL)

    async def _shutdown(_event=None):
        if runtime.get("stopped"):
            return
        runtime["stopped"] = True
        cancel_poll()
        cancel_stop()
        await hass.async_add_executor_job(runtime["api"].stop)

    cancel_stop = hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _shutdown)
    runtime["shutdown"] = _shutdown


def _setup_switches(hass, config, add_entities, runtime):
    """Start serial communication in the executor."""
    _LOGGER.info("Setting up plcbus devices")

    device_name = config.get(CONF_DEVICE) or get_plcbus_interface()
    if not device_name:
        raise PLCBUSException(
            "No PLCBUS serial device found. Reconfigure PLCBus with a device path."
        )
    switches = runtime["switches"]
    houses = runtime["houses"]
    user_code = config.get(CONF_USER_CODE)
    devices = config.get(CONF_UNIT) or []

    def _known_units():
        return {entity.unit_code for entity in switches}

    @callback
    def _handle_command(message):
        if runtime.get("stopped"):
            return
        if not runtime.get("ready"):
            runtime["pending"].append(message)
            return
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

    def commandCB(message):
        hass.add_job(_handle_command, message)

    Api = PLCBUSAPI(logging, device_name, commandCB, messageCB)
    runtime["api"] = Api

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

    @callback
    def _ready():
        runtime["ready"] = True
        for message in runtime["pending"]:
            _handle_command(message)
        runtime["pending"].clear()

    hass.add_job(_ready)
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
