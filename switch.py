"""Support for plcbus switches."""
import logging
from typing import Optional


import voluptuous as vol

from .lib.plcbus_lib import PLCBUSAPI, PLCBUSException, get_plcbus_interface


import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.switch import PLATFORM_SCHEMA
from homeassistant.helpers.entity import ToggleEntity

_LOGGER = logging.getLogger(__name__)

DOMAIN = "plcbus"

ENTITY_ID_FORMAT = DOMAIN + ".{}"

CONF_DEVICE = 'device'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_DEVICE, default=get_plcbus_interface()): cv.string,
})
PlcbusSwitchList = []



def setup_platform(hass, config, add_entities, discovery_info=None):
    _LOGGER.info("Setting up plcbus devices ", )

    device_name = config.get(CONF_DEVICE)
    Api = PLCBUSAPI(logging,device_name,commandCB,messageCB)
    entities = []
    house = "D1"
    devices = ["A1","A2","A3","A4","B6","B7","B8","B9"]
    _LOGGER.info ("devices= %s",devices)
    for device in devices:
        _LOGGER.info("device= %s",device)
        entities.append(PlcbusSwitch(Api, device, house))
    add_entities(entities, True)
    return True

def commandCB(self):
    _LOGGER.info("commandCB")
    if self['d_command']=="GET_ALL_ID_PULSE":
        _LOGGER.info ("get all id pulse reponse  %s",self)
        

    else:
        _LOGGER.info (self)
        _LOGGER.info("Current status for %s, is %s", self['d_home_unit'], self['d_command'])
        for entity in PlcbusSwitchList:
            if (entity._device_code == self['d_home_unit']) :
                _LOGGER.info("Device exists set status for %s", entity.name)
                if (self['d_command'] == "STATUS_ON") :
                    entity.set_state(True)
                elif (self['d_command'] == "STATUS_OFF") :
                    entity.set_state(False)
                elif (self['d_command'] == "ON") :
                    entity.set_state(True)
                elif (self['d_command'] == "OFF") :
                    entity.set_state(False)

def messageCB(self):
    _LOGGER.info ("messageCB")

class PlcbusSwitch(ToggleEntity):
    """Representation of a Plcbus switch."""

    def __init__(self,plcbus_API, device_code, house_code) -> None:
        """Initialize the Wifi switch."""
        self._name = "Switch-" + device_code
        self._state = None
        self._plcbus_API = plcbus_API
        self._device_code = device_code
        self._house_code = house_code
        PlcbusSwitchList.append(self)

    @property
    def name(self) -> str:
        """Return the name of the switch."""
        return self._name

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self._state

    def set_state(self, state):
        """Turn the switch on or off."""
        self._state = state

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        self._plcbus_API.send("ON",self._device_code,self._house_code)

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        self._plcbus_API.send("OFF",self._device_code,self._house_code)

    def update(self):
        """Get the state and update it."""
        self._plcbus_API.send("STATUS_REQUEST",self._device_code,self._house_code)

