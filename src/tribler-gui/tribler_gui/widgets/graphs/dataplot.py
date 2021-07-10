import pyqtgraph as pg
from pyqtgraph import DateAxisItem

from tribler_gui.utilities import format_size
from tribler_gui.widgets.graphs.timeseriesplot import TimeSeriesPlot


class DataAxisItem(pg.AxisItem):
    def tickStrings(self, values, scale, spacing):
        return [format_size(value, precision=3) for value in values]


class TimeSeriesDataPlot(TimeSeriesPlot):

    def __init__(self, parent, name, series, **kargs):
        axis_items = {'bottom': DateAxisItem('bottom'), 'left': DataAxisItem('left')}
        super().__init__(parent, name, series, axis_items=axis_items, **kargs)
