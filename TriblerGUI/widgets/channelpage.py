from __future__ import absolute_import

from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QWidget

from TriblerGUI.utilities import get_image_path
from TriblerGUI.widgets.tablecontentmodel import TorrentsContentModel
from TriblerGUI.widgets.triblertablecontrollers import TorrentsTableViewController


class ChannelPage(QWidget):
    """
    The ChannelPage displays a list of a channel's contents.
    """

    def __init__(self):
        QWidget.__init__(self)
        self.channel_info = None
        self.model = None
        self.controller = None

    def initialize_channel_page(self):
        self.model = TorrentsContentModel()
        self.controller = TorrentsTableViewController(self.model, self.window().channel_page_container,
                                                      None, self.window().channel_torrents_filter_input)

        # Remove the commit control from the delegate for performance
        commit_control = self.window().channel_page_container.content_table.delegate.commit_control
        self.window().channel_page_container.content_table.delegate.controls.remove(commit_control)

    def initialize_with_channel(self, channel_info):
        self.channel_info = channel_info

        self.window().channel_preview_label.setHidden(channel_info['subscribed'])
        self.window().channel_back_button.setIcon(QIcon(get_image_path('page_back.png')))

        # initialize the page about a channel
        self.window().channel_name_label.setText(channel_info['name'])
        self.window().num_subs_label.setText(str(channel_info['votes']))
        self.window().subscription_widget.initialize_with_channel(channel_info)
        self.window().channel_page_container.details_container.hide()

        self.window().channel_page_container.content_table.on_torrent_clicked.connect(self.on_torrent_clicked)

        self.model.channel_pk = channel_info['public_key']
        self.load_torrents()

    def on_torrent_clicked(self, torrent_info):
        self.window().channel_page_container.details_container.show()
        self.window().channel_page_container.details_tab_widget.update_with_torrent(torrent_info)

    def load_torrents(self):
        self.controller.model.reset()
        self.controller.load_torrents(1, 50)  # Load the first 50 torrents
