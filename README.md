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

After installing and restarting Home Assistant:

1. Open **Settings > Devices & services > Add integration**.
2. Search for **PLCBus**.
3. Enter the serial device path, two-digit hexadecimal user code, and optional
   comma-separated units, such as `A1,A2,B6`.

Leave the device blank to detect a Prolific PL2303 adapter. A stable
`/dev/serial/by-id/...` path is recommended. The device must be accessible to
Home Assistant. If it cannot be opened, Home Assistant reports a setup error and
retries; the form validates configuration but does not send commands to test hardware.

Use the integration's menu and **Reconfigure** to change these settings.
Only one PLCBus serial connection is supported. Reconfiguring or removing the
integration closes its connection and cancels its polling callbacks.

### Migrating existing YAML

Existing configuration is imported automatically into a configuration entry:

```YAML
switch:
  - platform: plcbus
    device: '/dev/ttyUSB0'
    user_code: "D1"
    unit: [A1,A2,A3,A4,B6,B7,B8,B9]
```
After the integration appears under **Devices & services**, remove the PLCBus
switch platform from `configuration.yaml`. Subsequent changes should be made
through **Reconfigure**: YAML is ignored if an entry already exists, preventing
duplicate serial connections. Existing switch unique IDs are preserved when
the user code and unit addresses are unchanged.

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

## Development tests

The tests cover configuration, YAML import, reconfiguration, duplicate prevention,
serial shutdown, and Home Assistant event-loop scheduling with a simulated adapter.
They do not replace testing on physical PLCBUS hardware.

```sh
python -m pip install -r requirements-test.txt
python -m pytest -q -o asyncio_default_fixture_loop_scope=function tests/test_plcbus.py
```
