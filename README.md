[![hacs_badge](https://img.shields.io/badge/HACS-Default-green.svg)](https://github.com/custom-components/hacs)
[![GitHub release](https://img.shields.io/github/release/tikismoke/home-assistant-plcbus)](https://GitHub.com/tikismoke/home-assistant-plcbus/releases/)
[![GitHub license](https://img.shields.io/github/license/tikismoke/home-assistant-plcbus)](https://github.com/tikismoke/home-assistant-plcbus/blob/master/LICENSE)
# home-assistant-plcbus


This is a try to make plcbus available in Home Assistant

Let see what future give us.

Configuration YAML looks like:

```YAML
switch:
  - platform: plcbus
    device: '/dev/ttyUSB0'
    user_code: D1
    unit: [A1,A2,A3,A4,B6,B7,B8,B9]    
```
Where we define a platform for switchlike this:

device: is OPTIONAL it could be find itself by the lib if it's a prolific 2303

user_code: (hex format) USER CODE as defined in PLCbus docs from 00 to FF (0 to 255)

unit: a comma separated list of unit address tp use as switch (Home_Code from A to K + Unit_Code from 1 to 11)

note the [ ] arround the list....

If you do not know you unit_code at start the components ask all available unit_code search in log for something like this:

```
INFO (Thread-2) [custom_components.plcbus.switch] Find a device with unit_code A1
INFO (Thread-2) [custom_components.plcbus.switch] Find a device with unit_code B6
```
