from __future__ import absolute_import
from __future__ import division

import time

import pyqtgraph as pg

from TriblerGUI.defs import BITTORRENT_BIRTHDAY
from TriblerGUI.widgets.graphs.DateAxisItem import DateAxisItem

YEAR_SECONDS = 365 * 24 * 3600


class TimeSeriesPlot(pg.PlotWidget):

    def __init__(self, parent, name, series, **kargs):
        axisItems = {'bottom': DateAxisItem('bottom')}
        super(TimeSeriesPlot, self).__init__(parent=parent, title=name, axisItems=axisItems, **kargs)
        self.getPlotItem().showGrid(x=True, y=True)
        self.setBackground('#202020')
        self.setAntialiasing(True)
        self.setMenuEnabled(False)

        self.series = None
        self.plot_data = [[], []]
        self.plots = []
        self.series = series
        self.last_timestamp = 0

        legend = pg.LegendItem((150, 25 * len(series)), offset=(150, 30))
        legend.setParentItem(self.graphicsItem())

        for serie in series:
            self.plot_data[1].append([])

            plot = self.plot(**serie)
            self.plots.append(plot)
            legend.addItem(plot, serie['name'])

        # Limit the date range
        self.setLimits(xMin=BITTORRENT_BIRTHDAY, xMax=time.time()+YEAR_SECONDS)

    def setup_labels(self):
        pass

    def reset_plot(self):
        self.plot_data = [[], [[] for _ in self.plots]]

    def add_data(self, timestamp, data, skip_old=False):
        if skip_old and timestamp < self.last_timestamp:
            return
        self.plot_data[0].append(timestamp)
        for i, data_item in enumerate(data):
            self.plot_data[1][i].append(data_item)
        self.last_timestamp = timestamp

    def render_plot(self):
        for i, plot in enumerate(self.plots):
            plot.setData(y=pg.np.array(self.plot_data[1][i]), x=pg.np.array(self.plot_data[0]))

