import time

import pyqtgraph as pg

from tribler_gui.defs import BITTORRENT_BIRTHDAY
from tribler_gui.widgets.graphs.DateAxisItem import DateAxisItem, YEAR_SPACING


class TimeSeriesPlot(pg.PlotWidget):
    def __init__(self, parent, name, series, **kargs):
        axisItems = {'bottom': DateAxisItem('bottom')}
        super(TimeSeriesPlot, self).__init__(parent=parent, title=name, axisItems=axisItems, **kargs)
        self.getPlotItem().showGrid(x=True, y=True)
        self.setBackground('#202020')
        self.setAntialiasing(True)
        self.setMenuEnabled(False)

        self.plot_data = {}
        self.plots = []
        self.series = series
        self.last_timestamp = 0

        legend = pg.LegendItem((150, 25 * len(series)), offset=(150, 30))
        legend.setParentItem(self.graphicsItem())

        for serie in series:
            plot = self.plot(**serie)
            self.plots.append(plot)
            legend.addItem(plot, serie['name'])

        # Limit the date range
        self.setLimits(xMin=BITTORRENT_BIRTHDAY, xMax=time.time() + YEAR_SPACING)

    def setup_labels(self):
        pass

    def reset_plot(self):
        self.plot_data = {}

    def add_data(self, timestamp, data):
        self.plot_data[timestamp] = data

    def render_plot(self):
        # Sort the plot data before rendering via plot.setData() to prevent loops and extra lines in the graph.
        self.plot_data = dict(sorted(self.plot_data.items(), key=lambda x: x[0]))
        print(self.plot_data)

        for i, plot in enumerate(self.plots):
            plot.setData(
                x=pg.np.array(list(self.plot_data.keys())), y=pg.np.array([data[i] for data in self.plot_data.values()])
            )
