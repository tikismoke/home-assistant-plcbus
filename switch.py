"""Support for plcbus switches."""
import logging
from typing import Optional


import voluptuous as vol

from lib.plcbus_lib import PLCBUSAPI, PLCBUSException

from homeassistant.components.switch import DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType
import homeassistant.helpers.config_validation as cv
from homeassistant.const import STATE_OFF, STATE_ON

_LOGGER = logging.getLogger(__name__)

ENTITY_ID_FORMAT = DOMAIN + ".{}"

DOMAIN = "plcbus"

def setup_platform(hass, config, add_entities, discovery_info=None):
    _LOGGER.info("Setting up plcbus devices ", )
    Api = PLCBUSAPI(logging,"/dev/ttyUSB0",commandCB,messageCB)
    entities = []
    house="D1"
    device="A3"
    for devices in device:
        entities.append(PlcbusSwitch(Api, device, house))
    add_entities(entities, True)
    return True


def commandCB(self):
    print("commandCB")
    if self['d_command']=="GET_ALL_ID_PULSE":
        print ("get all id pulse reponse",self)
        for entity in PlcbusSwitch:
            print (PlcbusSwitch.device_info())

    else:
        print (self)
        print("Current status for %s, is %s", self['d_home_unit'], self['d_command'])
        for entity in PlcbusSwitch:
            if (entity._device_code == self['d_home_unit']):
                print("Device exists:")
                print (PlcbusSwitch.device_info())
            else :
                print("status for not known device")

def messageCB(self):
    print ("messageCB")

class PlcbusSwitch(Api,device_code,house_code):
    """Representation of a Plcbus switch."""

    def __init__(self) -> None:
        """Initialize the Wifi switch."""
        self._name = "Switch"
        self._state = None
        self._API = API
        self._device_code = device_code
        self._house_code = house_code

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
        _state = state

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        await self.Api.send("ON",_device_code,_house_code)

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        await self.Api.send("OFF",_device_code,_house_code)

    async def async_update(self):
        """Get the state and update it."""
        await self.Api.send("STATUS_REQUEST",_device_code,_house_code)

