"""Shared PLCBUS configuration validation."""

import voluptuous as vol

from .const import CONF_DEVICE, CONF_UNIT, CONF_USER_CODE


def normalize_user_code(value):
    """Validate and normalize a two-digit hexadecimal user code."""
    if not isinstance(value, str) or len(value) != 2:
        raise vol.Invalid("user_code must contain exactly two hexadecimal digits")
    if any(char not in "0123456789abcdefABCDEF" for char in value):
        raise vol.Invalid("user_code must contain exactly two hexadecimal digits")
    return value.upper()


def normalize_unit_code(value):
    """Validate and normalize a house and unit address."""
    if not isinstance(value, str):
        raise vol.Invalid("unit must be a house code A-P followed by a unit 1-16")
    value = value.upper()
    if len(value) < 2 or value[0] not in "ABCDEFGHIJKLMNOP":
        raise vol.Invalid("unit must be a house code A-P followed by a unit 1-16")
    suffix = value[1:]
    if (
        len(suffix) > 2
        or not suffix.isascii()
        or not suffix.isdigit()
        or not 1 <= int(suffix) <= 16
    ):
        raise vol.Invalid("unit must be a house code A-P followed by a unit 1-16")
    return f"{value[0]}{int(suffix)}"


def normalize_config(config):
    """Normalize UI or imported configuration."""
    device = config.get(CONF_DEVICE, "")
    if not isinstance(device, str):
        raise vol.Invalid("device must be a serial device path")
    units = config.get(CONF_UNIT, [])
    if isinstance(units, str):
        units = units.split(",") if units.strip() else []
    if not isinstance(units, list):
        raise vol.Invalid("unit must be a list or comma-separated addresses")
    normalized_units = []
    for unit in units:
        if not isinstance(unit, str):
            raise vol.Invalid("unit addresses must be strings")
        normalized_units.append(normalize_unit_code(unit.strip()))
    return {
        CONF_DEVICE: device.strip(),
        CONF_USER_CODE: normalize_user_code(config.get(CONF_USER_CODE)),
        CONF_UNIT: list(dict.fromkeys(normalized_units)),
    }
