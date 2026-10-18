"""Keep the recorder from storing noise. Nothing here depends on Home Assistant.

Home Assistant stores a new row whenever a state changes. With a 5 s poll a
voltage that flickers in its last digit, or a BMS clock that ticks, adds
thousands of rows a day that carry no information. Alarms and protections are
binary sensors and do not pass through these helpers, so they still change at once.
"""

from datetime import datetime

# A change of one last digit must stay this long before it is shown.
STEP_HOLD_SECONDS = 60

# The BMS clock is shown again after this time, or at once when it drifts.
CLOCK_REFRESH_SECONDS = 15 * 60
CLOCK_DRIFT_SECONDS = 60
CLOCK_FORMAT = "%Y-%m-%d %H:%M:%S"


class StepHold:
    """Shows a measurement, but holds back a change of a single step.

    step is the last digit of the value, for example 1 mV for a cell. A change
    of two steps or more is shown at once. A change of one step is shown once it
    has been there for hold_seconds without going back, so a value that flickers
    between 3281 mV and 3282 mV stays at 3281 mV.
    """

    def __init__(self, step, hold_seconds=STEP_HOLD_SECONDS):
        self.step = step
        self.hold_seconds = hold_seconds
        self.shown = None
        self._since = None

    def update(self, value, now):
        """Feed the newest value at monotonic time now and return what to show."""
        if value is None or self.shown is None:
            self.shown = value
            self._since = None
            return value
        difference = abs(value - self.shown)
        if difference == 0:
            self._since = None
            return self.shown
        # 1.5 steps leaves room for float noise such as 0.0010000000000003.
        if difference > self.step * 1.5:
            self.shown = value
            self._since = None
            return value
        if self._since is None:
            self._since = now
        if now - self._since >= self.hold_seconds:
            self.shown = value
            self._since = None
        return self.shown


class ClockHold:
    """Shows the BMS clock again only when it drifts or a refresh is due.

    The clock changes on every settings read, about every minute. Its useful
    content is how far it is off, so a new reading is shown when that offset
    changes by CLOCK_DRIFT_SECONDS, for example after the clock was set, and
    otherwise every CLOCK_REFRESH_SECONDS.
    """

    def __init__(self, refresh_seconds=CLOCK_REFRESH_SECONDS, drift_seconds=CLOCK_DRIFT_SECONDS):
        self.refresh_seconds = refresh_seconds
        self.drift_seconds = drift_seconds
        self.shown = None
        self._offset = None
        self._shown_at = None

    def update(self, stamp, now):
        """Feed the BMS clock text and the local time (naive datetime) and return what to show."""
        if stamp is None:
            self.shown = None
            return None
        try:
            clock = datetime.strptime(stamp, CLOCK_FORMAT)
        except (TypeError, ValueError):
            self.shown = stamp
            return stamp
        offset = (clock - now).total_seconds()
        if (
            self.shown is None
            or abs(offset - self._offset) >= self.drift_seconds
            or (now - self._shown_at).total_seconds() >= self.refresh_seconds
        ):
            self.shown = stamp
            self._offset = offset
            self._shown_at = now
        return self.shown


# Digits published per value type. Power is in kW; the BMS reports it from 0.01 V x 0.01 A,
# so anything below a whole watt (0.001 kW) is noise. Energy counters step in 0.01 kWh
# (10 Wh), which is finer than the hourly statistics of the Energy dashboard.
POWER_DIGITS = 3
ENERGY_DIGITS = 2


def rounded(value, digits):
    """round() that lets a missing value through."""
    if value is None:
        return None
    return round(float(value), digits)
