[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)

[![GitHub Release](https://img.shields.io/github/release/samuolis/brink.svg?style=for-the-badge&color=blue)](https://github.com/samuolis/brink/releases) 

![Project Maintenance](https://img.shields.io/badge/maintainer-Lukas%20Samuolis-blue.svg?style=for-the-badge)

# Brink-Home Ventilation

Custom component for Home Assistant. This component is designed to integrate the [Brink-Home](https://www.brink-home.com/) systems with [ebus Brink Emodule](https://www.brinkclimatesystems.nl/documenten/brink-home-emodule-imodule-614491.pdf).

<img width="503" alt="Screenshot 2023-05-08 at 21 14 39" src="https://user-images.githubusercontent.com/28056781/236899814-e903fbb0-e007-4938-aa2c-0e04e91fbb36.png">

## Installation

You have two options for installation:

### HACS

- Go to the [HACS](https://hacs.xyz) panel
- Go to integrations 
- Search for 'Brink-Home ventilations'
- Click \'Download this repository with HACS'.

### Manually

- Copy "brink_home" folder to the "/config/custom_components" folder.
- Restart HA server.

### WORKING ON:
- Brink Renovent 180
- Brink Renovent 300
- Brink Renovent 400 Plus
- Brink Flair 325
- Please tell me, it should work with all Brink ventilation systems

## What's New in 2.0.0

- **v1.1 API migration** — Switched from old portal API (5 parameters, cookie auth) to v1.1 API (20+ parameters, OIDC Bearer auth with PKCE)
- **New sensors** — Supply/exhaust air flow, fresh air/supply temperatures, humidity, CO2 (4 sensors), days since filter reset, remaining duration, active control status, bypass valve status, preheater status
- **Ventilation level select** — Level control moved from fan entity to a select dropdown (Level 0-3), auto-switches to Manual mode
- **New select entities** — Operating mode (Auto/Manual/Holiday/Party/Night), bypass operation
- **Filter status** — Binary sensor for filter change indication
- **Live config updates** — Configurable polling interval (minimum 15s) applies immediately without restart
- **Error handling** — User-visible notifications for API and connection errors
- **Security hardened** — OIDC PKCE with state validation, trusted-domain redirect enforcement, credential cleanup on unload, input sanitization
