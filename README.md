[![HACS](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://www.hacs.xyz/docs/faq/custom_repositories/)
[![Latest release](https://img.shields.io/github/v/release/demonio669/home-assistant-plcbus)](https://github.com/demonio669/home-assistant-plcbus/releases)

## Installation with HACS

This repository is not part of the HACS default store. Add it as a custom repository:

1. In Home Assistant, open **HACS > Integrations**.
2. Open the menu and choose **Custom repositories**.
3. Add `https://github.com/demonio669/home-assistant-plcbus` and select **Integration** as the category.
4. Install **PLCBus** from HACS and restart Home Assistant.

Alternatively, copy `custom_components/plcbus` into the `custom_components` directory of your Home Assistant configuration and restart.

## Configuration

The integration is configured in `configuration.yaml`:

```YAML
switch:
  - platform: plcbus
    device: '/dev/ttyUSB0'
    user_code: D1
    unit: [A1,A2,A3,A4,B6,B7,B8,B9]    
```
Configuration options:

- `device` (optional): serial device path. If omitted, the integration attempts to find a Prolific PL2303 adapter.
- `user_code` (required): two-digit hexadecimal PLCBUS user code (`00` to `FF`).
- `unit` (optional): list of house/unit addresses, such as `A1` or `B6`. If omitted, the integration searches for available units and logs discoveries.

Automatic unit discovery currently queries house codes A through K. Explicit addresses support house codes A through P and unit numbers 1 through 16.

Discovered units are logged, for example:

```
INFO [custom_components.plcbus.switch] Find a device with unit_code A1
INFO [custom_components.plcbus.switch] Find a device with unit_code B6
```

## Limitations

Only switch control is supported; dimming, brightness, and scenes are not implemented. A PLCBUS serial adapter is required.
