[![hacs_badge](https://img.shields.io/badge/HACS-Default-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)

[![GitHub Release](https://img.shields.io/github/release/samuolis/brink.svg?style=for-the-badge&color=blue)](https://github.com/samuolis/brink/releases)

![Project Maintenance](https://img.shields.io/badge/maintainer-Lukas%20Samuolis-blue.svg?style=for-the-badge)

# Brink-Home Ventilation

A custom [Home Assistant](https://www.home-assistant.io/) integration for [Brink](https://www.brink-home.com/) ventilation systems. This integration connects to the Brink Home cloud portal to provide monitoring and control of your Brink heat recovery ventilation unit directly from Home Assistant.

Brink Home is a cloud service that allows remote monitoring and control of Brink residential ventilation systems equipped with the [Brink eModule/iModule](https://www.brinkclimatesystems.nl/documenten/brink-home-emodule-imodule-614491.pdf). This integration polls the Brink Home API to expose sensors, controls, and diagnostics as Home Assistant entities.

## Supported Devices

| Device | Status |
|---|---|
| Brink Flair 325 | Confirmed |
| Brink Renovent 180 | Confirmed |
| Brink Renovent 300 | Confirmed |
| Brink Renovent 400+ | Confirmed |

Any Brink ventilation device that is visible and controllable through the [Brink Home portal](https://www.brink-home.com) should work with this integration. If you have a different Brink model that works, please open an issue to let us know.

## Supported Functions

The integration exposes up to 20 parameters from the Brink Home API as Home Assistant entities. The exact entities available depend on your device model and connected sensors.

### Sensors

| Entity | Unit | Description | Default |
|---|---|---|---|
| Supply air flow rate | m³/h | Current supply air volume flow | Enabled |
| Exhaust air flow rate | m³/h | Current exhaust air volume flow | Enabled |
| Fresh air temperature | °C | Outside air temperature at intake | Enabled |
| Supply temperature | °C | Air temperature after heat recovery | Enabled |
| Relative humidity | % | Indoor relative humidity | Disabled |
| Days since filter reset | days | Counter since last filter replacement | Enabled |
| Remaining duration | minutes | Time remaining in current timed mode (Party, Night, Holiday) | Disabled |
| Active control status | enum | Current control source (Standby, Manual, Holiday, Party, Auto CO2, Auto eBus, etc.) | Disabled |
| Bypass valve status | enum | Bypass valve state (Init, Opening, Closing, Open, Closed) | Enabled |
| Preheater status | enum | Preheater state (Off, Auto, Lock current, Lock maximum) | Enabled |
| CO2 sensor 1 | ppm | CO2 concentration from sensor 1 | Disabled |
| CO2 sensor 2 | ppm | CO2 concentration from sensor 2 | Disabled |
| CO2 sensor 3 | ppm | CO2 concentration from sensor 3 | Disabled |
| CO2 sensor 4 | ppm | CO2 concentration from sensor 4 | Disabled |
| Extra ventilation remaining | minutes | Countdown timer for active extra ventilation boost | Enabled |
| Current season | enum | Current season (Summer/Winter) based on outdoor temperature vs freezing threshold | Enabled |
| Humidity change sensor 1 (3 min) | % | Humidity change for monitored sensor 1 in the last 3 minutes. Shows unavailable when no sensor is assigned. | Enabled |
| Humidity change sensor 2 (3 min) | % | Humidity change for monitored sensor 2 in the last 3 minutes. Shows unavailable when no sensor is assigned. | Enabled |
| Humidity change sensor 3 (3 min) | % | Humidity change for monitored sensor 3 in the last 3 minutes. Shows unavailable when no sensor is assigned. | Enabled |

### Select Controls

| Entity | Options | Description |
|---|---|---|
| Operating mode | Automatic, Manual, Holiday, Party, Night | Sets the ventilation operating mode |
| Bypass operation | Automatic, Bypass closed, Bypass open | Controls the bypass valve for free cooling |
| Ventilation level | Level 0, Level 1, Level 2, Level 3, Adaptive (HA) | Sets the ventilation fan speed. Adaptive (HA) enables humidity-responsive automatic control. |

### Binary Sensors

| Entity | Description |
|---|---|
| Filter status | Indicates whether the filter needs replacement (on = dirty) |

### Switch Controls

| Entity | Description |
|---|---|
| Extra ventilation | Toggle switch for timed ventilation boost at the seasonal max level. ON = boost active, OFF = cancel boost. |

Entities marked "Disabled" in the Default column are created but disabled by default. Enable them in **Settings > Devices & Services > Entities** if your device has the corresponding sensor hardware (e.g., CO2 sensors, humidity sensor).

## Installation

### HACS (Recommended)

1. Open [HACS](https://hacs.xyz/) in Home Assistant.
2. Go to **Integrations**.
3. Click the three-dot menu in the top right and select **Custom repositories**.
4. Add the repository URL and select **Integration** as the category.
5. Search for "Brink-Home Ventilation" and click **Download**.
6. Restart Home Assistant.

### Manual Installation

1. Download the latest release from the [GitHub releases page](https://github.com/samuolis/brink/releases).
2. Copy the `brink_ventilation` folder into your Home Assistant `custom_components` directory (e.g., `/config/custom_components/brink_ventilation/`).
3. Restart Home Assistant.

## Configuration

### Initial Setup

1. Go to **Settings > Devices & Services**.
2. Click **Add Integration**.
3. Search for "Brink-Home Ventilation".
4. Enter your Brink Home portal credentials:
   - **Email**: The email address you use to log into [www.brink-home.com](https://www.brink-home.com).
   - **Password**: Your Brink Home portal password.
5. Click **Submit**. The integration will authenticate with the Brink Home portal and discover your ventilation device(s).

### Options

After setup, configure the integration options:

1. Go to **Settings > Devices & Services**.
2. Find the Brink-Home Ventilation integration and click **Configure**.
3. The options flow has three pages:

#### General Settings

| Option | Default | Range | Description |
|---|---|---|---|
| Scan interval | 60 | 15–300 seconds | How often to poll the Brink Home API |
| Freezing threshold | -2 | -10 to +10 °C | Temperature below which winter mode activates |
| Temperature source | _(Brink sensor)_ | Entity selector | Optional: override with any HA temperature sensor |

#### Extra Ventilation

| Option | Default | Range | Description |
|---|---|---|---|
| Boost duration | 120 | 15–480 minutes | How long the extra ventilation boost runs |
| Summer max level | 3 | 1–3 | Ventilation level during boost in summer |
| Winter max level | 2 | 1–3 | Ventilation level during boost in winter (lower to save preheater electricity) |

#### Adaptive (HA) Mode

| Option | Default | Range | Description |
|---|---|---|---|
| Summer base level | 2 | 0–3 | Normal ventilation level in summer |
| Winter base level | 1 | 0–3 | Normal ventilation level in winter |
| Humidity sensor 1–3 | _(empty)_ | Entity selector | Up to 3 humidity sensors to monitor for spikes |
| Humidity spike threshold | 5 | 1–60 % | Humidity increase within 3 minutes that triggers extra ventilation |

## Removal

1. Go to **Settings > Devices & Services**.
2. Find **Brink-Home Ventilation**.
3. Click the three-dot menu and select **Delete**.
4. Restart Home Assistant (optional, but recommended to clean up fully).

## Extra Ventilation

The **Extra ventilation** switch activates a timed ventilation boost. When turned on:

1. The integration checks the current outdoor temperature against the freezing threshold.
2. If above the threshold (summer), ventilation is set to the **summer max level**.
3. If below the threshold (winter), ventilation is set to the **winter max level** — lower to reduce preheater electricity usage.
4. The device is switched to Manual mode and the boost runs for the configured duration.
5. After the timer expires, ventilation returns to the previous state.

The winter/summer split exists because Brink ventilation units have a preheater that prevents freezing of the heat exchanger. At high flow rates in freezing conditions, the preheater uses significant electricity. Setting a lower max level in winter avoids this.

## Adaptive (HA) Mode

Select **Adaptive (HA)** in the ventilation level control to enable automatic humidity-responsive ventilation:

1. The device is set to Manual mode at the seasonal **base level** (summer or winter, depending on outdoor temperature).
2. Up to 3 humidity sensors are monitored. If any sensor detects a rapid humidity increase (configurable threshold) within 3 minutes — for example, from someone taking a shower — the **extra ventilation boost** is automatically triggered.
3. After the boost timer expires, ventilation returns to the seasonal base level.
4. If the outdoor temperature crosses the freezing threshold (season changes), ventilation levels are automatically adjusted.

### How Humidity Spike Detection Works

- The integration monitors configured humidity sensors, sampling at most every 30 seconds.
- It maintains a 3-minute rolling window of readings per sensor.
- If the difference between the newest and oldest reading in the window exceeds the spike threshold, extra ventilation is triggered.
- The **Humidity change sensor** entities (one per configured sensor) show the current delta, which helps you fine-tune the threshold by reviewing their history.

### Internet Resilience

If the internet connection is lost when a ventilation level change is needed:

- The command is queued and automatically retried on each polling cycle.
- Once connectivity is restored, the queued command is sent and normal operation resumes.

## Data Update Strategy

This is a **cloud polling** integration. It periodically fetches data from the Brink Home API.

- **Default polling interval**: 60 seconds (configurable in integration options, minimum 15 seconds).
- **Expedited polling**: After a write command (changing mode, ventilation level, or bypass), the polling interval is temporarily reduced to 15 seconds for 3 minutes so that changes are reflected quickly.
- **Authentication**: Uses OIDC with PKCE (OAuth 2.0) for secure authentication with the Brink Home portal.
- **Coordinator pattern**: Uses Home Assistant's `DataUpdateCoordinator` so all entities share a single polling cycle, minimizing API calls.

## Known Limitations

- **Cloud-only**: Requires a Brink Home portal account at [www.brink-home.com](https://www.brink-home.com). There is no local API available.
- **Write commands require gateway connectivity**: Changing operating mode, ventilation level, or bypass requires the gateway (eModule/iModule) to be online. If the gateway is offline, a repair issue will appear in Home Assistant.
- **Optional sensors disabled by default**: Sensors for CO2, humidity, remaining duration, and active control status are disabled by default. Enable them in entity settings if your device has the corresponding hardware.
- **Polling-based updates**: Changes made outside Home Assistant (e.g., via the Brink Home app or physical controls) may take up to one polling interval to appear.
- **Old portal API for writes**: Write commands use the legacy portal API due to Brink API limitations. Read operations use the newer v1.1 API.

## Troubleshooting

| Problem | Solution |
|---|---|
| "Can't connect" error during setup | Check your internet connection. Verify the [Brink Home portal](https://www.brink-home.com) is accessible in your browser. |
| "Email or password is incorrect" error | Double-check your credentials by logging into [www.brink-home.com](https://www.brink-home.com) directly. |
| Entities show "Unavailable" | Check that your Brink device is powered on and connected to the internet. Check the Brink Home app to see if the device is online. |
| Write commands fail | Check the **Repairs** section in Home Assistant. A "Gateway not available" issue means the eModule/iModule is offline. Verify the device has power and internet connectivity. |
| Session expired / re-authentication needed | Go to **Settings > Devices & Services**, find the integration, and click **Reconfigure** to enter your password again. |
| Sensors show unexpected values | Some sensors (e.g., CO2) will report 0 if the corresponding hardware is not installed. Disable these entities if they are not relevant to your setup. |
| Integration not found after install | Make sure you restarted Home Assistant after installing via HACS or manually. |
| Extra ventilation not triggering from humidity | Check the "Humidity change sensor" history to see if spikes are reaching your configured threshold. Try lowering the threshold. Ensure humidity sensors are connected and reporting values. |
| Adaptive (HA) mode not switching levels | Verify the freezing threshold and temperature source in options. Check the "Current season" sensor to see which season is active. |
| Commands queued but not executing | Check internet connectivity. Queued commands are retried automatically on each polling cycle. |

## Automation Examples

### Alert when filter needs changing

```yaml
automation:
  - alias: "Brink filter dirty notification"
    trigger:
      - platform: state
        entity_id: binary_sensor.brink_ventilation_XXXX_filter_status
        to: "on"
    action:
      - service: notify.notify
        data:
          title: "Brink Ventilation"
          message: "The ventilation filter needs to be replaced."
```

### Switch to party mode when guests arrive

```yaml
automation:
  - alias: "Party mode when guests"
    trigger:
      - platform: state
        entity_id: input_boolean.guests_present
        to: "on"
    action:
      - service: select.select_option
        target:
          entity_id: select.brink_ventilation_XXXX_mode
        data:
          option: "Party"
```

### Boost ventilation when CO2 is high

```yaml
automation:
  - alias: "Boost ventilation on high CO2"
    trigger:
      - platform: numeric_state
        entity_id: sensor.brink_ventilation_XXXX_co2_sensor_1
        above: 1000
    action:
      - service: select.select_option
        target:
          entity_id: select.brink_ventilation_XXXX_ventilation_level
        data:
          option: "Level 3"
```

### Night mode on a schedule

```yaml
automation:
  - alias: "Brink night mode at bedtime"
    trigger:
      - platform: time
        at: "22:30:00"
    action:
      - service: select.select_option
        target:
          entity_id: select.brink_ventilation_XXXX_mode
        data:
          option: "Night"
```

### Boost ventilation with a switch

```yaml
automation:
  - alias: "Extra ventilation from dashboard"
    trigger:
      - platform: state
        entity_id: input_boolean.extra_ventilation_trigger
        to: "on"
    action:
      - service: switch.turn_on
        target:
          entity_id: switch.brink_ventilation_XXXX_extra_ventilation
      - service: input_boolean.turn_off
        target:
          entity_id: input_boolean.extra_ventilation_trigger
```

Replace `XXXX` in entity IDs with your device's system ID. You can find the correct entity IDs in **Settings > Devices & Services > Entities**.

## Use Cases

- **Monitor indoor air quality**: Track CO2 levels, humidity, and temperatures to understand your home's air quality over time.
- **Automate ventilation based on occupancy or air quality**: Increase ventilation when CO2 rises or when rooms are occupied, and reduce it when the house is empty.
- **Filter replacement notifications**: Get alerted when the filter needs changing, instead of checking manually.
- **Schedule ventilation modes**: Automatically switch to Night mode at bedtime and back to Automatic in the morning.
- **Party and event ventilation**: Boost airflow during gatherings and return to normal afterward.
- **Energy-aware ventilation**: Monitor supply and exhaust temperatures to understand heat recovery efficiency, and use bypass control for free cooling on mild days.
- **Humidity-responsive ventilation**: Automatically boost ventilation when bathroom humidity spikes from showers, and return to normal when done.
- **Season-aware energy savings**: Reduce ventilation levels in winter to minimize preheater electricity usage while maintaining comfort.
