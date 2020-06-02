"""Support for plcbus switches."""
import logging
from datetime import timedelta
from typing import Optional

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchDevice
from homeassistant.helpers.entity import Entity, ToggleEntity

from .lib.plcbus_lib import PLCBUSAPI, PLCBUSException, get_plcbus_interface

_LOGGER = logging.getLogger(__name__)

DOMAIN = "plcbus"

ENTITY_ID_FORMAT = DOMAIN + ".{}"

CONF_USER_CODE = 'user_code'
CONF_DEVICE = 'device'
CONF_UNIT = 'unit'


SCAN_INTERVAL = timedelta(seconds=60)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USER_CODE): cv.string,
    vol.Optional(CONF_DEVICE, default=get_plcbus_interface()): cv.string,
    vol.Optional(CONF_UNIT, default=[]): vol.All(cv.ensure_list_csv, [cv.string]),
})

PlcbusSwitchList = []

def setup_platform(hass, config, add_entities, discovery_info=None):
    _LOGGER.info("Setting up plcbus devices ", )
 
    def commandCB(self):
        _LOGGER.debug("commandCB")
        if self['d_command']=="GET_ALL_ID_PULSE":
            # Used to ask plcbus to find all device within the house
            # Some modules might not answer and need to be added manually
            device_found = []
            _LOGGER.debug ("get all id pulse reponse  %s",self)
            _LOGGER.debug ("data1=%s",self['d_data1'])
            _LOGGER.debug ("data2=%s",self['d_data2'])
            for i in range(0, 8):
                if self['d_data2'] >> i & 1:
                    _LOGGER.info ("Find a device with unit_code %s", self['d_home_unit'][0] + str(i+1))
                    # TODO find a way to not add discovered one automatically if already configured
                    device_found.append(PlcbusSwitch(Api, self['d_home_unit'][0] + str(i+1), user_code, "mdi:electric-switch"))
            for i in range(0, 8):
                if self['d_data1'] >> i & 1:
                    _LOGGER.info ("Find a device with unit_code %s", self['d_home_unit'][0] + str(i+9))
                    # TODO find a way to not add discovered one automatically if already configured
                    device_found.append(PlcbusSwitch(Api, self['d_home_unit'][0] + str(i+9), user_code, "mdi:electric-switch"))
            device_found.append(PlcbusUnitDataUpdate(Api, self['d_home_unit'], user_code,))
            add_entities(device_found, True)
        elif self['d_command']=="GET_ALL_ON_ID_PULSE":
            _LOGGER.debug ("get all on id pulse reponse  %s",self)
            _LOGGER.debug ("data1=%s",self['d_data1'])
            _LOGGER.debug ("data2=%s",self['d_data2'])
            for i in range(0, 8):
                if self['d_data2'] >> i & 1:
                    _LOGGER.info ("Find device that is on with unit_code %s", self['d_home_unit'][0] + str(i+1))
                    for entity in PlcbusSwitchList:
                        if (entity._unit_code == self['d_home_unit'][0] + str(i+1)) :
                            entity.set_state(True)
                            ToggleEntity.async_write_ha_state(entity)
            for i in range(0, 8):
                if self['d_data1'] >> i & 1:
                    _LOGGER.info ("Find device that is on with unit_code %s", self['d_home_unit'][0] + str(i+9))
                    for entity in PlcbusSwitchList:
                        if (entity._unit_code == self['d_home_unit'][0] + str(i+9)) :
                            entity.set_state(True)
                            ToggleEntity.async_write_ha_state(entity)
        else:
            _LOGGER.debug (self)
            _LOGGER.debug("receive %s, for unit %s", self['d_command'], self['d_home_unit'])
            for entity in PlcbusSwitchList:
                if (entity._unit_code == self['d_home_unit']) :
                    _LOGGER.debug("Device exists %s", entity.name)
                    if (self['d_command'] == "STATUS_ON") :
                        entity.set_state(True)
                        _LOGGER.debug("Set TRUE %s", entity.name)
                    elif (self['d_command'] == "STATUS_OFF") :
                        entity.set_state(False)
                        _LOGGER.debug("Set FALSE %s", entity.name)
                    elif (self['d_command'] == "ON") :
                        entity.set_state(True)
                        _LOGGER.debug("Set TRUE %s", entity.name)
                    elif (self['d_command'] == "OFF") :
                        entity.set_state(False)
                        _LOGGER.debug("Set FALSE %s", entity.name)
                    ToggleEntity.async_write_ha_state(entity)

    def messageCB(self):
        _LOGGER.info ("messageCB")

    device_name = config.get(CONF_DEVICE)
    Api = PLCBUSAPI(logging,device_name,commandCB,messageCB)
    user_code = config.get(CONF_USER_CODE)
    entities = []
    devices = config.get(CONF_UNIT)
    _LOGGER.info ("devices= %s",devices)

    # TODO replace when ok
    #for unit_code in map(chr, range(ord('A'), ord('C')+1)):
    for unit_code in map(chr, range(ord('A'), ord('K')+1)):
        _LOGGER.debug ("GET_ALL_ID_PULSE unit_code= %s",unit_code)
        Api.send("GET_ALL_ID_PULSE",unit_code,user_code)
        #entities.append(PlcbusUnitDataUpdate(Api, unit_code, user_code,))

    #_LOGGER.debug ("device_found= %s",device_found)
    for device in devices:
        _LOGGER.info("device= %s",device)
        entities.append(PlcbusSwitch(Api, device, user_code, "mdi:electric-switch"))
    add_entities(entities, True)
    return True

class PlcbusSwitch(SwitchDevice):
    """Representation of a Plcbus switch."""

    def __init__(self,plcbus_API, unit_code, user_code, icon) -> None:
        """Initialize the Wifi switch."""
        self._name = "PlcbusSwitch_" + user_code + "_" + unit_code
        self._state = None
        self._plcbus_API = plcbus_API
        self._unit_code = unit_code
        self._user_code = user_code
        self._icon = icon
        self._unique_id = self._name
        PlcbusSwitchList.append(self)
        _LOGGER.debug("Creating switch device= %s with name %s",self._unit_code, self._name)

    @property
    def should_poll(self):
        """No need to poll. entity update is done by get_all_on_id_pulse."""
        return False

    @property
    def name(self) -> str:
        """Return the name of the switch."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return the unique ID for this sensor."""
        return f"{self._unique_id}"

    @property
    def icon(self) -> str:
        """Return the mdi icon of the entity."""
        return self._icon

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self._state

    def set_state(self, state):
        """Turn the switch on or off."""
        self._state = state

    def turn_on(self, **kwargs):
        """Turn the switch on."""
        self._is_on = True
        self._plcbus_API.send("ON",self._unit_code,self._user_code)

    def turn_off(self, **kwargs):
        """Turn the switch off."""
        self._is_on = False
        self._plcbus_API.send("OFF",self._unit_code,self._user_code)

class PlcbusUnitDataUpdate(Entity):
    """Class to manage fetching plcbus all_on_id_pulse."""

    def __init__(self, plcbus_API, unit_code, user_code):
        """Initialize."""
        self._user_code = user_code
        self._plcbus_API = plcbus_API
        self._unit_code = unit_code

    def update(self):
        """Get the state and update it."""
        _LOGGER.debug("GET_ALL_ON_ID_PULSE unit_code= %s",self._unit_code)
        self._plcbus_API.send("GET_ALL_ON_ID_PULSE",self._unit_code,self._user_code)

    @property
    def available(self):
        """Not available for HA."""
        return "False"
    
    @property
    def assumed_state(self):
        """Always OFF for HA."""
        return "False"

    @property
    def hidden(self):
        """Not shown on HA."""
        return "False"
