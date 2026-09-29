"""Unit conversions and BMS value cleanup that do not depend on Home Assistant."""

NOMINAL_LFP_CELL_VOLTAGE = 3.2


def volts_from_millivolts(millivolts):
    """Cell voltages are parsed in mV. Home Assistant should show volts."""
    if millivolts is None:
        return None
    return round(float(millivolts) / 1000.0, 3)


def watts_from_kilowatts(kilowatts):
    """Pack power is calculated in kW. Publish it in watts."""
    if kilowatts is None:
        return None
    return round(float(kilowatts) * 1000.0, 1)


def kwh_from_amp_hours(amp_hours, cell_count, volts_per_cell=NOMINAL_LFP_CELL_VOLTAGE):
    """Turn a BMS amp-hour counter into kWh with a fixed LFP cell voltage.

    A fixed voltage keeps the result monotonic. Multiplying by the live pack
    voltage would make the counter fall whenever the pack sags under load.
    """
    if amp_hours is None or not cell_count or cell_count <= 0:
        return None
    return round(float(amp_hours) * int(cell_count) * float(volts_per_cell) / 1000.0, 3)


def present_temperatures(values):
    """Keep each BMS slot. None means that socket has no probe fitted.

    An empty socket is sent as 0 K, which is about -273 °C. A fitted probe
    keeps its own number, even when a lower slot is empty.
    """
    slots = []
    for value in values or []:
        try:
            celsius = float(value)
        except (TypeError, ValueError):
            slots.append(None)
            continue
        slots.append(round(celsius, 2) if -40.0 <= celsius <= 125.0 else None)
    return slots


def resolve_soc(raw_soc, remain_ah, full_ah):
    """Use remain/full when the SOC byte is missing or above 100 percent."""
    full_ah = float(full_ah or 0)
    remain_ah = float(remain_ah or 0)
    if raw_soc is None or (raw_soc > 100 and full_ah > 0):
        if full_ah > 0:
            return round(remain_ah / full_ah * 100.0, 1)
        return 0.0
    return round(float(raw_soc), 1)


def resolve_soh(raw_soh, full_ah, design_ah):
    """Use full/design when SOH is missing, 0, or above 100 percent."""
    full_ah = float(full_ah or 0)
    design_ah = float(design_ah or 0)
    if raw_soh is None or raw_soh == 0 or raw_soh > 100:
        if design_ah > 0 and full_ah > 0:
            return round(full_ah / design_ah * 100.0, 1)
        if raw_soh is None:
            return 100.0
        if raw_soh == 0:
            return 0.0
    return round(float(raw_soh), 1)


# A real lifetime counter stays within this many full cycles of the design capacity.
# The bytes on these packs decode to the same multi-billion Ah value for charge
# and discharge, which is a misread field, not throughput.
MAX_THROUGHPUT_CYCLES = 2000


def bms_throughput_kwh(amp_hours, other_amp_hours, cell_count, design_ah):
    """Return kWh from a BMS Ah counter, or None when the counter looks unused.

    Some Pace frames copy the design capacity into both cumulative counters.
    Others repeat one implausible integer for charge and discharge.
    """
    if amp_hours is None:
        return None
    amp_hours = float(amp_hours)
    if amp_hours <= 0:
        return None
    if design_ah:
        design_ah = float(design_ah)
        if amp_hours > design_ah * MAX_THROUGHPUT_CYCLES:
            return None
        if other_amp_hours is not None:
            other_amp_hours = float(other_amp_hours)
            if abs(amp_hours - design_ah) < 1.0 and abs(other_amp_hours - design_ah) < 1.0:
                return None
    return kwh_from_amp_hours(amp_hours, cell_count)


def integrate_energy_kwh(charged_kwh, discharged_kwh, power_watts, elapsed_seconds):
    """Add power over an interval. Ignores gaps longer than five minutes."""
    charged_kwh = float(charged_kwh or 0.0)
    discharged_kwh = float(discharged_kwh or 0.0)
    if elapsed_seconds is None or elapsed_seconds <= 0 or elapsed_seconds > 300:
        return charged_kwh, discharged_kwh
    kilowatt_hours = abs(float(power_watts)) * float(elapsed_seconds) / 3600.0 / 1000.0
    if power_watts >= 0:
        charged_kwh += kilowatt_hours
    else:
        discharged_kwh += kilowatt_hours
    return charged_kwh, discharged_kwh
