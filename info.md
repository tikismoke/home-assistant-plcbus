[![hacs_badge](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub release](https://img.shields.io/github/release/tikismoke/home-assistant-plcbus)](https://GitHub.com/tikismoke/home-assistant-plcbus/releases/)
[![GitHub license](https://img.shields.io/github/license/tikismoke/home-assistant-plcbus)](https://github.com/tikismoke/home-assistant-plcbus/blob/master/LICENSE)
# PLCBus

hassio support for PLCBus.

![ScreenShot](plcbusswitch.png)

This is a try to make plcbus available in Home Assistant

Let see what future give us.
## Getting started

Download
```
/custom_components/plcbus/
```
into
```
<config directory>/custom_components/plcbus/
```
**Example configuration.yaml:**

```yaml
# Example configuration.yaml entry
switch:
  - platform: plcbus
    device: '/dev/ttyUSB0'
    user_code: D1
    unit: [A1,A2,A3,A4,B6,B7,B8,B9]
```
### Configuration Variables

**device**

  (string) (OPTIONAL) it could be find itself by the lib if it's a prolific 2303

**user_code**

  (hex format)(Required) USER CODE as defined in PLCbus docs from 00 to FF (0 to 255)

**unit**

  (comma_list)(Optional) a comma separated list of unit address tp use as switch (Home_Code from A to K + Unit_Code from 1 to 11)
  note the [ ] arround the list....

## Limitations

Limit to switch for the moment (No DIM/BRIGHTNESS/SCENES/etc.)

## Known Issues

* A lot

* No translations available yet


## Hardware Requirements

A plcbus adapter
