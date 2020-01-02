"""
This class is derived from pull request #74 submitted by @3rdcycle to pyqtgraph.
As time of this writing the PR is still open so we can remove this file later
when the PR is merged.
https://github.com/pyqtgraph/pyqtgraph/pull/74
"""
import time
from datetime import datetime

import numpy as np

from pyqtgraph import AxisItem

__all__ = ['DateAxisItem', 'ZoomLevel']

MS_SPACING = 1 / 1000.0
SECOND_SPACING = 1
MINUTE_SPACING = 60
HOUR_SPACING = 3600
DAY_SPACING = 24 * HOUR_SPACING
WEEK_SPACING = 7 * DAY_SPACING
MONTH_SPACING = 30 * DAY_SPACING
YEAR_SPACING = 365 * DAY_SPACING


def makeMSStepper(stepSize):
    def stepper(val, n):
        val *= 1000
        f = stepSize * 1000
        return (val // (n * f) + 1) * (n * f) / 1000.0

    return stepper


def makeSStepper(stepSize):
    def stepper(val, n):
        return (val // (n * stepSize) + 1) * (n * stepSize)

    return stepper


def makeMStepper(stepSize):
    def stepper(val, n):
        d = datetime.utcfromtimestamp(val)
        base0m = d.month + n * stepSize - 1
        d = datetime(d.year + base0m // 12, base0m % 12 + 1, 1)
        return (d - datetime(1970, 1, 1)).total_seconds()

    return stepper


def boundTimestamp(value):
    # if value < 0:
    #     return 0
    # elif value > 3155760000:  # 100 years
    #     return 3155760000
    return value


def makeYStepper(stepSize):
    def stepper(val, n):
        d = datetime.utcfromtimestamp(boundTimestamp(val))
        next_date = datetime((d.year // (n * stepSize) + 1) * (n * stepSize), 1, 1)
        return (next_date - datetime(1970, 1, 1)).total_seconds()

    return stepper


class TickSpec(object):
    """ Specifies the properties for a set of date ticks and computes ticks
    within a given utc timestamp range """

    def __init__(self, spacing, stepper, timeFormat, autoSkip=None):
        """
        ============= ==========================================================
        Arguments
        spacing       approximate (average) tick spacing
        stepper       a stepper function that takes a utc time stamp and a step
                      steps number n to compute the start of the next unit. You
                      can use the make_X_stepper functions to create common
                      steppers.
        timeFormat    a strftime compatible format string which will be used to
                      convert tick locations to date/time strings
        autoSkip      list of step size multipliers to be applied when the tick
                      density becomes too high. The tick spec automatically
                      applies additional powers of 10 (10, 100, ...) to the list
                      if necessary. Set to None to switch autoSkip off
        ============= ==========================================================

        """
        self.spacing = spacing
        self.step = stepper
        self.format = timeFormat
        self.autoSkip = autoSkip

    def makeTicks(self, minVal, maxVal, minSpc):
        ticks = []
        n = self.skipFactor(minSpc)
        x = self.step(minVal, n)
        while x <= maxVal:
            ticks.append(x)
            x = self.step(x, n)
        return (np.array(ticks), n)

    def skipFactor(self, minSpc):
        if self.autoSkip is None or minSpc < self.spacing:
            return 1
        factors = np.array(self.autoSkip)
        while True:
            for f in factors:
                spc = self.spacing * f
                if spc > minSpc:
                    return f
            factors *= 10


class ZoomLevel(object):
    """ Generates the ticks which appear in a specific zoom level """

    def __init__(self, tickSpecs):
        """
        ============= ==========================================================
        tickSpecs     a list of one or more TickSpec objects with decreasing
                      coarseness
        ============= ==========================================================

        """
        self.tickSpecs = tickSpecs
        self.utcOffset = 0

    def tickValues(self, minVal, maxVal, minSpc):
        # return tick values for this format in the range minVal, maxVal
        # the return value is a list of tuples (<avg spacing>, [tick positions])
        # minSpc indicates the minimum spacing (in seconds) between two ticks
        # to fullfill the maxTicksPerPt constraint of the DateAxisItem at the
        # current zoom level. This is used for auto skipping ticks.
        allTicks = []
        valueSpecs = []
        # back-project (minVal maxVal) to UTC, compute ticks then offset to
        # back to local time again
        utcMin = minVal - self.utcOffset
        utcMax = maxVal - self.utcOffset
        for spec in self.tickSpecs:
            ticks, skipFactor = spec.makeTicks(utcMin, utcMax, minSpc)
            # reposition tick labels to local time coordinates
            ticks += self.utcOffset
            # remove any ticks that were present in higher levels
            tick_list = [x for x in ticks.tolist() if x not in allTicks]
            allTicks.extend(tick_list)
            valueSpecs.append((spec.spacing, tick_list))
            # if we're skipping ticks on the current level there's no point in
            # producing lower level ticks
            if skipFactor > 1:
                break
        return valueSpecs


YEAR_MONTH_ZOOM_LEVEL = ZoomLevel(
    [
        TickSpec(YEAR_SPACING, makeYStepper(1), '%Y', autoSkip=[1, 5, 10, 25]),
        TickSpec(MONTH_SPACING, makeMStepper(1), '%b'),
    ]
)
MONTH_DAY_ZOOM_LEVEL = ZoomLevel(
    [
        TickSpec(MONTH_SPACING, makeMStepper(1), '%b'),
        TickSpec(DAY_SPACING, makeSStepper(DAY_SPACING), '%d', autoSkip=[1, 5]),
    ]
)
DAY_HOUR_ZOOM_LEVEL = ZoomLevel(
    [
        TickSpec(DAY_SPACING, makeSStepper(DAY_SPACING), '%a %d'),
        TickSpec(HOUR_SPACING, makeSStepper(HOUR_SPACING), '%H:%M', autoSkip=[1, 6]),
    ]
)
HOUR_MINUTE_ZOOM_LEVEL = ZoomLevel(
    [
        TickSpec(DAY_SPACING, makeSStepper(DAY_SPACING), '%a %d'),
        TickSpec(MINUTE_SPACING, makeSStepper(MINUTE_SPACING), '%H:%M', autoSkip=[1, 5, 15]),
    ]
)
HMS_ZOOM_LEVEL = ZoomLevel(
    [TickSpec(SECOND_SPACING, makeSStepper(SECOND_SPACING), '%H:%M:%S', autoSkip=[1, 5, 15, 30])]
)
MS_ZOOM_LEVEL = ZoomLevel(
    [
        TickSpec(MINUTE_SPACING, makeSStepper(MINUTE_SPACING), '%H:%M:%S'),
        TickSpec(MS_SPACING, makeMSStepper(MS_SPACING), '%S.%f', autoSkip=[1, 5, 10, 25]),
    ]
)


class DateAxisItem(AxisItem):
    """ An AxisItem that displays dates from unix timestamps

    The display format is adjusted automatically depending on the current time
    density (seconds/point) on the axis.
    You can customize the behaviour by specifying a different set of zoom levels
    than the default one. The zoomLevels variable is a dictionary with the
    maximum number of seconds/point which are allowed for each ZoomLevel
    before the axis switches to the next coarser level.

    """

    def __init__(self, orientation, **kvargs):
        super(DateAxisItem, self).__init__(orientation, **kvargs)
        # Set the zoom level to use depending on the time density on the axis
        self.utcOffset = time.timezone - 3600 * time.localtime().tm_isdst
        self.zoomLevel = YEAR_MONTH_ZOOM_LEVEL
        # we need about 60pt for our largest label
        self.maxTicksPerPt = 1 / 60.0
        self.zoomLevels = {
            self.maxTicksPerPt: MS_ZOOM_LEVEL,
            30 * self.maxTicksPerPt: HMS_ZOOM_LEVEL,
            15 * 60 * self.maxTicksPerPt: HOUR_MINUTE_ZOOM_LEVEL,
            6 * 3600 * self.maxTicksPerPt: DAY_HOUR_ZOOM_LEVEL,
            5 * 3600 * 24 * self.maxTicksPerPt: MONTH_DAY_ZOOM_LEVEL,
            3600 * 24 * 30 * self.maxTicksPerPt: YEAR_MONTH_ZOOM_LEVEL,
        }

    def tickStrings(self, values, scale, spacing):
        tickSpecs = self.zoomLevel.tickSpecs
        tickSpec = next((s for s in tickSpecs if s.spacing == spacing), None)
        dates = [datetime.utcfromtimestamp(v - self.utcOffset) for v in values]
        formatStrings = []
        for x in dates:
            try:
                if '%f' in tickSpec.format:
                    # we only support ms precision
                    formatStrings.append(x.strftime(tickSpec.format)[:-3])
                else:
                    formatStrings.append(x.strftime(tickSpec.format))
            except ValueError:  # Windows can't handle dates before 1970
                formatStrings.append('')
        return formatStrings

    def tickValues(self, minVal, maxVal, size):
        density = (maxVal - minVal) / size
        self.setZoomLevelForDensity(density)
        minSpacing = density / self.maxTicksPerPt
        values = self.zoomLevel.tickValues(minVal, maxVal, minSpc=minSpacing)
        return values

    def setZoomLevelForDensity(self, density):
        keys = sorted(self.zoomLevels.keys())
        key = next((k for k in keys if density < k), keys[-1])
        self.zoomLevel = self.zoomLevels[key]
        self.zoomLevel.utcOffset = self.utcOffset
