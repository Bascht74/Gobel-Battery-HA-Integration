---
description: 
---

# Changelog

## [2.4.11] - 2026-09-29
### Changed
-   Temperature sensors are created only for probes that report a real value. Empty sockets are not shown.

---------------

## [2.4.10] - 2026-09-29
### Changed
-   Internal Pace Wi-Fi no longer creates the charge and discharge limit sensors. The pushed frames do not contain them.

---------------

## [2.4.9] - 2026-09-29
### Fixed
-   After a dongle reboot or firmware update the TCP connection is opened again. A Home Assistant reload is no longer required.

---------------

## [2.4.8] - 2026-09-29
### Changed
-   On RS232, configuration is shown only for the master pack. The other packs keep their own measurements.

---------------

## [2.4.7] - 2026-09-29
### Added
-   Pace firmware (C1), hardware version (C6) and serial number (C2) are shown on the Home Assistant device.
-   Heater and communication faults are binary sensors.

---------------

## [2.4.6] - 2026-09-29
### Added
-   Pace setup tries TCP ports 9999 and 8899 before asking for a port.
-   Expert mode has a button that writes the current local time to the BMS clock. The clock sensor stays.

---------------

## [2.4.5] - 2026-09-29
### Added
-   Expert mode can switch the Pace buzzer and the LED alarm. Shutdown stays unavailable.

---------------

## [2.4.4] - 2026-09-29
### Added
-   If the typed TCP port does not answer, setup tries 9999 and 8899.

---------------

## [2.4.3] - 2026-09-29
### Changed
-   The Pace choices are now named Pace BMS and Pace BMS, internal Wi-Fi.

---------------

## [2.4.2] - 2026-09-29
### Added
-   Read-only Pace sensors for calibrated capacity, the BMS clock, CAN and RS485 protocol, plus buzzer and LED status. Expert mode does not turn these into controls.

---------------

## [2.4.1] - 2026-09-29
### Added
-   Network setup probes a Pace battery. A command reply is saved as active Pace. A pushed stream is saved as receive-only Pace. The BMS type names say which is which.

---------------

## [2.4.0] - 2026-09-29
### Added
-   The Pace/TDT protection and system pages from PBmsTools: cell and pack over/undervoltage, current delays, fast discharge current, short-circuit delay, balance, sleep, full charge, temperature protections and the limiter start current. They are configuration sensors, and the same names become number controls in expert mode.

---------------

## [2.3.1] - 2026-09-29
### Changed
-   Read-only configuration sensors and the expert-mode number, switch and select controls use the same names and stay in the Configuration category. The current limiter is configuration as well.
-   Entity names are translated for English, German, Simplified Chinese, Spanish and French.

---------------

## [2.3.0] - 2026-09-29
### Added
-   Expert mode in the integration options. It is off by default and asks for confirmation before it is enabled. While it is on, Pace and TDT configuration is writable: charge and discharge alarm/limit as number boxes, charge MOSFET, discharge MOSFET and the current limiter as switches, and the limiter gear as a select. The matching read-only sensors are removed. Turning the option off restores the sensors. JK and passive Pace WiFi stay read-only. Written current limits are positive amps.

---------------

## [2.2.1] - 2026-09-29
### Fixed
-   Pace discharge current limit. Real PBmsTools and esphome-pace-bms frames return the discharge threshold as a negative two's-complement word (110 A is `FF92`). Treating it as an unsigned word produced a value above 65000 A. Charge limits stay unsigned amps. The protection threshold is the limit; the alarm threshold is an entity attribute.

### Added
-   Design capacity, highest and lowest cell voltage, cell delta and the cell numbers of those extremes. These values were already in the analog frame. JK also gets a named MOS temperature.

---------------

## [2.2.0] - 2026-09-29
### Changed
-   Cell voltages are published in V with three decimal places. Power is in W. Energy is in kWh.
-   Individual cell voltages, min/max/delta, SOH, cycles and warnings stay under Diagnostic. Charge and discharge current limits stay under Configuration. SOC, pack voltage, current, power, temperature and energy stay on the device page.

### Added
-   [PACE/TDT] Charge current limit and discharge current limit via protocol commands D9H and DBH. The protection threshold (amps) is the limit. Polled at most once a minute. Passive Pace WiFi does not send these commands.
-   Tests for unit conversion, SOC/SOH fallback, energy integration, Pace limit frames and the JK power sign.
-   Integrated energy is stored on disk, so a reload no longer starts the estimated counter at 0.

### Notes
-   Pace cumulative charge/discharge in the analog frame is amp-hours, not kWh. When that counter looks real it is converted with 3.2 V per cell and used as the energy sensor, so the number comes from the BMS. JK has no lifetime energy counter, so those packs still integrate power locally and keep the last value across restarts.

---------------

## [2.1.0] - 2026-09-28
### Added
-   [Config] Reconfigure flow so host, port, serial device, BMS type and poll interval can be changed without deleting the integration. A Configure menu edits poll interval, parallel-pack limit and the JK display index.
-   [Statistics] Energy charged / energy discharged sensors (`Wh`, `total_increasing`) so long-term statistics and the Energy dashboard work. Cycle count is `total_increasing`.
-   [Entities] Primary readings stay on the device page. BMS limits are `config`. Cell voltages, SOH, cycles, warnings and balance flags are `diagnostic`.
-   [JKBMS] Charge current limit and discharge current limit (and related voltage setpoints) from the setup frame, shown under Configuration.
-   [PACE] Per-cell voltage warnings, temperature warnings, pack warning bits and balance-active sensors that the old add-on exposed.
-   [PACE] Cumulative charge/discharge counters from the analog frame (diagnostic, long-term statistics).

### Fixed
-   [JKBMS] Power follows the sign of the current, so discharge is negative (issue #29).
-   [PACE] Slave packs that report SOC above 100 (or SOH 0) fall back to remain/full and full/design (issue #28).
-   [JKBMS] Pack discovery waits a little longer so slower 4-pack broadcasts are less likely to be cut off (issue #11). This does not fix a bus that never broadcasts the missing packs.

### Not changed
-   Upstream pull requests are the author's own merges. Nothing external was left to port.
-   Pace CCL/DCL (issue #30) are not in the analog frame. JK limits are exposed; Pace still needs commands D9H/DBH, which are not polled yet.

---------------

## [2.0.12] - 2026-07-25

### Fixed
-   [JKBMS] Fixed setup frame voltage register parsing for `VolInverterMaxCharge` (Inverter Max Charge Voltage) at offset 38 and `VolFloatCharge` (Float Charge Voltage) at offset 42 (previously misidentified as battery undervoltage/overvoltage protection).

---------------

## [2.0.11] - 2026-07-13
### Fixed
-   [Pace BMS] Fixed false-positive structural matches in dynamic U/W byte calculation (e.g. when battery is fully charged and current is 0A) by checking for non-zero cell and temperature counts and utilizing a hybrid division calculation with fallback.

---------------

## [2.0.10] - 2026-06-24
### Fixed
-   [BMS] Fixed socket buffer truncation and telemetry protocol desynchronization over Ethernet/WiFi connections by implementing TCP stream buffering and reading until carriage return delimiter.

---------------

## [2.0.9] - 2026-06-22
### Fixed
-   [Integration] Fixed an issue where the integration would not automatically reconnect after a serial or network disconnection.
-   [JKBMS] Added a watchdog timer to force a connection reset if no valid telemetry frames are received for 15 seconds.
-   [PACE/TDT] Enhanced underlying communication handler to immediately discard dead connections upon read exceptions and reconnect on the next polling cycle.

---------------

## [2.0.8] - 2026-06-22
### Fixed
- Fixed `AttributeError: 'BMSCommunication' object has no attribute 'close'` during integration unload.



## 2.0.7

-   [Integration] Implement robust read retry mechanism and data caching for battery packs to smooth out intermittent RS485/Serial communication timeouts or CRC errors.
-   [Integration] Fix entities dropping to `unknown` state by ensuring they correctly transition to the standard `unavailable` state if communication with a battery pack completely drops or exceeds the retry limit.

---------------


## 2.0.6

-   [PACE/TDT] Fix active balancing status parsing incorrectly reporting values due to shifted byte offsets in RS232 and RS485 protocols.

---------------


## 2.0.1

-   [JKBMS] Fix multi-pack discovery and entity registration.
-   [JKBMS] Implement dynamic entity registration and unique physical `pack_id` mapping to prevent pack swapping and register newly online packs on the fly.
-   [JKBMS] Optimize startup passive listening wait window to ensure all parallel packs check in before completing the initial poll.

---------------


## 2.0.0

-   Migrate Home Assistant Add-on to native custom integration.

---------------


## 1.9.79

-   [JKBMS] Add support for publishing average cell voltage (`cell_voltage_avg`), maximum voltage cell index (`cell_voltage_max_index`), and minimum voltage cell index (`cell_voltage_min_index`) to Home Assistant via MQTT.
-   [JKBMS] Convert raw 0-based cell index telemetry values from the JK protocol to 1-based index sensors to align with standard cell naming.

---------------


## 1.9.78

-   [JKBMS] Fix 'Serial' object has no attribute 'gettimeout' AttributeError when connecting the BMS over a serial port in passive listening mode.

---------------


## 1.9.77

-   [PACE232] Implement robust structural validation for packet type classification. Distinguishes analog and warning packets by validating their schema structure for the reported number of parallel packs, automatically adapting to varying firmware data lengths (user-defined fields size U and warning status bytes W). This resolves protocol desync, cell voltage, temperature, and SOC telemetry corruption in multi-pack configurations.
-   [PACE/TDT] Fix IndexError parsing crashes on firmware versions without active balancing support by implementing safe boundary checks.
-   [PACE/TDT] Correct active balancing status byte offsets across PACE RS232, RS485, and TDT RS232 protocols.
-   [Dashboard] Add active and passive balancing status sensors to the PACE/TDT BMS pack details grid layout in the HA dashboard. Correct entity case mismatch (from uppercase SOC/SOH to lowercase soc/soh) to align with Home Assistant's automatically registered lowercase MQTT entity IDs.

---------------


## 1.9.74

-   [PACE/TDT] Separate Passive and Active Balancing Status into distinct sensors:
    *   **Passive Balancing Status**:
        *   Keys: `balancing_status_passive_1`, `balancing_status_passive_2`
        *   HA discovery name: `Pack 0x Balancing Status Passive 1 / 2`
        *   Value: Raw bitmask bypass-resistor active byte values (multiple bits can be 1).
    *   **Active Balancing Status**:
        *   Keys: `balancing_status_active_1`, `balancing_status_active_2`
        *   HA discovery name: `Pack 0x Balancing Status Active 1 / 2`
        *   Value: Decoded cell index (1-8, 9-16). Returns 0 when active balancing is inactive.
-   [TDT] Fix ValueError crash when balance state values are greater than 1.

---------------


## 1.9.73

-   [PACE/TDT] Add raw ASCII and Hexadecimal packet logging for all telemetry send and receive operations when `debug` configuration is enabled.
-   [PACE/TDT] Fix method signatures for capacity and product info methods.

---------------


## 1.9.72

-   [PACE/TDT] Expose active balancing status (`balance_state_1` and `balance_state_2`) sensors for PACE (RS232, RS485, WiFi) and TDT BMS protocols.
-   [BMS] Standardize debug logging format for parsed analog and warning telemetry across JK, PACE, and TDT BMS drivers.

---------------


## 1.9.71

-   [PACE485] Fix cell temperature sensors unit (from '℃' to standard '°C') so Home Assistant accepts the sensors.

---------------


## 1.9.70

-   [PACE232] Dynamically determine user-defined fields and warning status bytes parsing lengths to support differing battery pack firmware versions.
-   [PACE232] Implement a ratiometric packet classification method to differentiate Analog and Warning response packets. Delayed/out-of-order packets are salvaged, parsed, and cached to prevent Home Assistant sensor state corruption.

---------------


## 1.9.66

-   [Addon] Add multilingual translation support (English, Germany and Chinese) for configuration options to display user-friendly names and descriptions in the Home Assistant Add-on settings page.

---------------


## 1.9.61

-   [JKBMS] Add `jk_display_index_start` configuration setting with choices "00" or "01" (default) to allow matching the Home Assistant entity and pack labels with the physical dial-up address of the battery pack.

---------------


## 1.9.60

-   [JKBMS] Refactor JK BMS serial reader into an asynchronous background listener thread to completely prevent serial port blocking in the main loop. Non-55AA frames (like Modbus master queries) are automatically filtered and discarded. Main publishing logic fetches telemetry from thread-safe caches with 0.0s latency, resolving HA entity and pack count fluctuations.

---------------


## 1.9.59

-   [JKBMS] Make dynamic telemetry cache expiration adaptive based on the refresh interval (`max(30s, refresh_interval * 3)`) to support larger refresh interval settings (e.g. 20s) without false-offline reports.

---------------


## 1.9.58

-   [JKBMS] Optimize passive read loop by increasing reading timeout to 8.0s (fully covering the observed 7.0s cycle time for 16 packs) and adding a 5-second freshness cache bypass to prevent double reading from blocking the serial port.

---------------


## 1.9.57

-   [JKBMS] Further increase passive reading timeout window from 2.0s to 4.0s to guarantee a full 3.2-second sequential polling cycle of 16 packs is captured.

---------------


## 1.9.56

-   [JKBMS] Increase passive reading timeout window from 1.0s to 2.0s to reliably capture telemetry frames from up to 16 parallel battery packs.

---------------


## 1.9.55

-   [JKBMS] Cache dynamic telemetry frames for up to 30 seconds to prevent pack count (total_packs_num) and battery entities from fluctuating due to temporary packet drops or serial read timeouts.

---------------


## 1.9.54

-   [JKBMS] Map Modbus Slave ID directly as pack ID to support 0-based communication address configurations (addresses 0, 1, 2, 3...) and resolve pack mapping conflicts in Home Assistant.

---------------


## 1.9.53

-   [JKBMS] Map 1-based Modbus Slave ID in trailing ACK to 0-based pack ID to fix missing Pack 01 and prevent duplicate/misaligned pack devices in HA.

---------------


## 1.9.52

-   [PACEWIFI] Add support for PACE_LV_WIFI bms_type to passively parse telemetry data actively broadcasted over WiFi.

---------------


## 1.9.50

-   [JKBMS] Dynamically parse Modbus ACK at the end of frames, making data parsing independent of specific packet lengths.

---------------


## 1.9.48

-   [JKBMS] Fixed pack identification logic to prevent data collision between different packs.
-   [JKBMS] Send each pack's sensor data to its own separate Home Assistant device.

---------------


## 1.9.46

-   [JKBMS] Changed verbose frame-parsing log messages from WARNING to DEBUG to reduce log noise.

---------------


## 1.9.45

-   [JKBMS] Refined multi-pack integration and setup configuration parameters (Reg=0x161E).
-   [PACE232] Added heating film status (status_heating) to instruction_state.

---------------

## 1.9.21

-   Add build.yaml to fix Docker build failure (missing BUILD_FROM arg).


---------------

## 1.9.20

-   Add JK BMS RS485 support.
-   Fix Energy Discharged/Charged bug.


---------------

## 1.9.0

-   Auto reconnection after connection lost.
-   Add index of max/min cell voltage.
-   Modify Protoss PW10 / Waveshare manual, change 'Flow Control Settings' to 'Flow Control', 'Software Flow Control' to 'OFF'.


---------------

## 1.8.2

-   Fix temperature unit error.
-   Fix max/min voltage unit error.
-   Add voltage difference value.
-   Change data reading timeout to 3 seconds.

---------------


## 1.8.0

-   Value precision of energy charged/discharged is changed to 5.

---------------


## 1.7.8

-   TDT BMS bug fix.

---------------


## 1.7

-   fix RS232 multiple packs bug.
    for Pace BMS, use PACE_LV (latest version protocol) by default, if it does not work, try PACE_LV_V1.
-   add max/min cell voltage for whole system and each pack.
-   add TDT BMS support.

---------------