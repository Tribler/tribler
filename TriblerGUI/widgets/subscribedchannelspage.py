from __future__ import absolute_import

from PyQt5.QtWidgets import QWidget

from TriblerGUI.widgets.tablecontentmodel import ChannelsContentModel
from TriblerGUI.widgets.triblertablecontrollers import ChannelsTableViewController


class SubscribedChannelsPage(QWidget):
    """
    This page shows all the channels that the user has subscribed to.
    """

    def __init__(self):
        QWidget.__init__(self)
        self.dialog = None
        self.request_mgr = None
        self.model = None
        self.controller = None

    def initialize(self):
        self.model = ChannelsContentModel(subscribed=True)
        self.controller = ChannelsTableViewController(self.model, self.window().subscribed_channels_list,
                                                      self.window().num_subscribed_channels_label,
                                                      self.window().subscribed_channels_filter_input)

    def load_subscribed_channels(self):
        self.controller.model.reset()
        self.controller.load_channels(1, 50)  # Load the first 50 subscribed channels
