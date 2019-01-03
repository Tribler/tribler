from __future__ import absolute_import

from PyQt5.QtWidgets import QWidget

from TriblerGUI.widgets.tablecontentmodel import ChannelsContentModel
from TriblerGUI.widgets.triblertablecontrollers import ChannelsTableViewController


class DiscoveredPage(QWidget):
    """
    The DiscoveredPage shows an overview of all discovered channels in Tribler.
    """

    def __init__(self):
        QWidget.__init__(self)
        self.initialized = False
        self.model = None
        self.controller = None

    def initialize_discovered_page(self):
        if not self.initialized:
            self.initialized = True
            self.model = ChannelsContentModel()
            self.controller = ChannelsTableViewController(self.model, self.window().discovered_channels_list,
                                                          self.window().num_discovered_channels_label,
                                                          self.window().discovered_channels_filter_input)

    def load_discovered_channels(self):
        self.controller.model.reset()
        self.controller.load_channels(1, 50)  # Load the first 50 discovered channels
