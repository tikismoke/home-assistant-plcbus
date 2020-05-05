"""Support for Modbus switches."""
import logging
from typing import Optional


import voluptuous as vol

from homeassistant.components.switch import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_COMMAND_OFF,
    CONF_COMMAND_ON,
    CONF_NAME,
    CONF_SLAVE,
    STATE_ON,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity import ToggleEntity
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    CALL_TYPE_COIL,
    CALL_TYPE_REGISTER_HOLDING,
    CALL_TYPE_REGISTER_INPUT,
    CONF_COILS,
    CONF_HUB,
    CONF_REGISTER,
    CONF_REGISTER_TYPE,
    CONF_REGISTERS,
    CONF_STATE_OFF,
    CONF_STATE_ON,
    CONF_VERIFY_REGISTER,
    CONF_VERIFY_STATE,
    DEFAULT_HUB,
    MODBUS_DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


REGISTERS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_COMMAND_OFF): cv.positive_int,
        vol.Required(CONF_COMMAND_ON): cv.positive_int,
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_REGISTER): cv.positive_int,
        vol.Optional(CONF_HUB, default=DEFAULT_HUB): cv.string,
        vol.Optional(CONF_REGISTER_TYPE, default=CALL_TYPE_REGISTER_HOLDING): vol.In(
            [CALL_TYPE_REGISTER_HOLDING, CALL_TYPE_REGISTER_INPUT]
        ),
        vol.Optional(CONF_SLAVE): cv.positive_int,
        vol.Optional(CONF_STATE_OFF): cv.positive_int,
        vol.Optional(CONF_STATE_ON): cv.positive_int,
        vol.Optional(CONF_VERIFY_REGISTER): cv.positive_int,
        vol.Optional(CONF_VERIFY_STATE, default=True): cv.boolean,
    }
)

COILS_SCHEMA = vol.Schema(
    {
        vol.Required(CALL_TYPE_COIL): cv.positive_int,
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_SLAVE): cv.positive_int,
        vol.Optional(CONF_HUB, default=DEFAULT_HUB): cv.string,
    }
)

PLATFORM_SCHEMA = vol.All(
    cv.has_at_least_one_key(CONF_COILS, CONF_REGISTERS),
    PLATFORM_SCHEMA.extend(
        {
            vol.Optional(CONF_COILS): [COILS_SCHEMA],
            vol.Optional(CONF_REGISTERS): [REGISTERS_SCHEMA],
        }
    ),
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Read configuration and create Modbus devices."""
    switches = []
    if CONF_COILS in config:
        for coil in config[CONF_COILS]:
            hub_name = coil[CONF_HUB]
            hub = hass.data[MODBUS_DOMAIN][hub_name]
            switches.append(
                ModbusCoilSwitch(
                    hub, coil[CONF_NAME], coil[CONF_SLAVE], coil[CALL_TYPE_COIL]
                )
            )
            
    add_entities(switches)


class ModbusCoilSwitch(ToggleEntity, RestoreEntity):
    """Representation of a Modbus coil switch."""

    def __init__(self, hub, name, slave, coil):
        """Initialize the coil switch."""
        self._hub = hub
        self._name = name
        self._slave = int(slave) if slave else None
        self._coil = int(coil)
        self._is_on = None
        self._available = True

    async def async_added_to_hass(self):
        """Handle entity which will be added."""
        state = await self.async_get_last_state()
        if not state:
            return
        self._is_on = state.state == STATE_ON

    @property
    def is_on(self):
        """Return true if switch is on."""
        return self._is_on

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    def turn_on(self, **kwargs):
        """Set switch on."""
        self._write_coil(self._coil, True)

    def turn_off(self, **kwargs):
        """Set switch off."""
        self._write_coil(self._coil, False)

    def update(self):
        """Update the state of the switch."""
        self._is_on = self._read_coil(self._coil)

    def _read_coil(self, coil) -> Optional[bool]:
        """Read coil using the Modbus hub slave."""
        try:
            result = self._hub.read_coils(self._slave, coil, 1)
        except ConnectionException:
            self._available = False
            return

        if isinstance(result, (ModbusException, ExceptionResponse)):
            self._available = False
            return

        value = bool(result.bits[0])
        self._available = True

        return value

    def _write_coil(self, coil, value):
        """Write coil using the Modbus hub slave."""
        try:
            self._hub.write_coil(self._slave, coil, value)
        except ConnectionException:
            self._available = False
            return

        self._available = True
