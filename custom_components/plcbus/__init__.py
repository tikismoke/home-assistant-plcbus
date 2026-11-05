"""The PLCBUS component."""

from homeassistant.const import Platform

from .const import DOMAIN

PLATFORMS = [Platform.SWITCH]


async def async_setup_entry(hass, entry):
    """Load PLCBUS from a configuration entry."""
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass, entry):
    """Unload switches and stop the serial connection."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    runtime = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if runtime is not None:
        await runtime["shutdown"]()
    return True