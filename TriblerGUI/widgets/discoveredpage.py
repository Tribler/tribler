from __future__ import absolute_import

from PyQt5.QtWidgets import QWidget

from TriblerGUI.widgets.lazytableview import ACTION_BUTTONS


class DiscoveredPage(QWidget):
    """
    The DiscoveredPage shows an overview of all discovered channels in Tribler.
    """

    def __init__(self):
        QWidget.__init__(self)
        self.initialized = False

    def initialize_discovered_page(self):
        if not self.initialized:
            self.initialized = True
            container = self.window().discovered_channels_container

            container.initialize_model(search_type=u'channel')
            container.channel_entry_clicked.connect(self.window().on_channel_clicked)
            container.details_tab_widget.setHidden(True)
            container.buttons_container.setHidden(True)
            container.top_bar_container.setHidden(True)

            container.torrents_table.setColumnHidden(container.model.column_position[u'commit_status'], True)
            container.torrents_table.setColumnHidden(container.model.column_position[u'health'], True)
            container.torrents_table.setColumnHidden(container.model.column_position[ACTION_BUTTONS], True)

    def load_discovered_channels(self):
        self.window().discovered_channels_container.model.refresh()
