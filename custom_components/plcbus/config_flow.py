"""UI configuration and YAML import for PLCBUS."""

import logging

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import CONF_DEVICE, CONF_UNIT, CONF_USER_CODE, DOMAIN
from .lib.plcbus_lib import get_plcbus_interface
from .validation import normalize_config

_LOGGER = logging.getLogger(__name__)


def _schema(config):
    units = config.get(CONF_UNIT, [])
    if isinstance(units, list):
        units = ",".join(units)
    return vol.Schema(
        {
            vol.Optional(CONF_DEVICE, default=config.get(CONF_DEVICE, "")): str,
            vol.Required(CONF_USER_CODE, default=config.get(CONF_USER_CODE, "D1")): str,
            vol.Optional(CONF_UNIT, default=units): str,
        }
    )


class PLCBusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure one PLCBUS serial connection."""

    VERSION = 1

    async def _validate(self, user_input):
        config = normalize_config(user_input)
        if not config[CONF_DEVICE]:
            config[CONF_DEVICE] = await self.hass.async_add_executor_job(
                get_plcbus_interface
            )
            if not config[CONF_DEVICE]:
                raise vol.Invalid("No PLCBUS serial device found")
        return config

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Show the configuration form."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        errors = {}
        if user_input is not None:
            try:
                config = await self._validate(user_input)
            except vol.Invalid:
                errors["base"] = "invalid_config"
            except OSError:
                _LOGGER.exception("Failed to discover the PLCBUS serial adapter")
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="PLCBus", data=config)
        return self.async_show_form(
            step_id="user", data_schema=_schema(user_input or {}), errors=errors
        )

    async def async_step_import(self, user_input) -> FlowResult:
        """Import existing YAML without opening a second serial connection."""
        if self._async_current_entries():
            _LOGGER.warning(
                "PLCBus is already configured; ignoring YAML. "
                "Remove switch.plcbus from configuration.yaml and use Reconfigure."
            )
            return self.async_abort(reason="single_instance_allowed")
        try:
            config = await self._validate(user_input)
        except (vol.Invalid, OSError) as err:
            _LOGGER.error("Cannot import PLCBUS YAML configuration: %s", err)
            return self.async_abort(reason="invalid_config")
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(title="PLCBus", data=config)

    async def async_step_reconfigure(self, user_input=None) -> FlowResult:
        """Update the connection settings and reload the integration."""
        entry = self._get_reconfigure_entry()
        errors = {}
        if user_input is not None:
            try:
                config = await self._validate(user_input)
            except vol.Invalid:
                errors["base"] = "invalid_config"
            except OSError:
                _LOGGER.exception("Failed to discover the PLCBUS serial adapter")
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(entry, data_updates=config)
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_schema(user_input or entry.data),
            errors=errors,
        )
