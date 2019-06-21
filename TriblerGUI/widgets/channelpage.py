from __future__ import absolute_import

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QWidget

from TriblerGUI.utilities import format_votes, get_gui_setting, get_image_path
from TriblerGUI.widgets.tablecontentmodel import TorrentsContentModel
from TriblerGUI.widgets.triblertablecontrollers import TorrentsTableViewController


class ChannelPage(QWidget):
    """
    The ChannelPage displays a list of a channel's contents.
    """

    def __init__(self):
        QWidget.__init__(self)
        self.channel_info = {}
        self.model = None
        self.controller = None
        self.gui_settings = None

    def initialize_channel_page(self, gui_settings):
        self.gui_settings = gui_settings
        self.model = TorrentsContentModel(hide_xxx=get_gui_setting(self.gui_settings, "family_filter", True,
                                                                   is_bool=True) if self.gui_settings else True)
        self.window().core_manager.events_manager.node_info_updated.connect(self.model.update_node_info)
        self.window().core_manager.events_manager.node_info_updated.connect(self.on_node_info_update)
        self.controller = TorrentsTableViewController(self.model,
                                                      self.window().channel_page_container.content_table,
                                                      self.window().channel_page_container.details_container,
                                                      None, self.window().channel_torrents_filter_input)
        self.window().core_manager.events_manager.torrent_info_updated.connect(self.controller.update_health_details)

        self.window().channel_page_container.splitter.splitterMoved.connect(self.controller.brain_dead_refresh)

        # Remove the commit control from the delegate for performance
        commit_control = self.window().channel_page_container.content_table.delegate.commit_control
        self.window().channel_page_container.content_table.delegate.controls.remove(commit_control)

        # To reload the preview
        self.window().channel_preview_button.clicked.connect(self.preview_clicked)
        self.controller.count_query_complete.connect(self._on_query_complete)

    def on_node_info_update(self, update_dict):
        if "public_key" in update_dict and "id" in update_dict and self.channel_info and \
                self.channel_info["public_key"] == update_dict["public_key"] and\
                self.channel_info["id"] == update_dict["id"]:
            self.initialize_with_channel(update_dict)

    def preview_clicked(self):
        self.controller.fetch_preview()
        self.initialize_with_channel(self.channel_info)

    def initialize_with_channel(self, channel_info):
        # Turn off sorting by default to speed up SQL queries
        self.window().channel_page_container.content_table.horizontalHeader().setSortIndicator(-1, Qt.AscendingOrder)
        self.channel_info = channel_info
        self.model.channel_pk = channel_info['public_key']
        self.model.channel_id = channel_info['id']

        self.window().channel_preview_button.setHidden(channel_info['state'] in ('Complete', 'Legacy'))
        self.window().channel_back_button.setIcon(QIcon(get_image_path('page_back.png')))
        self.window().channel_page_container.content_table.setFocus()
        self.window().channel_page_container.details_container.hide()
        self.update_labels()
        self.window().channel_torrents_filter_input.setText("")
        self.load_torrents()

    def update_labels(self):
        # initialize the page about a channel
        self.window().channel_name_label.setText(self.channel_info['name'])

        color = '#FE6D01' if int(self.channel_info["subscribed"]) else '#fff'
        self.window().subscribe_button.setStyleSheet('border:none; color: %s' % color)
        self.window().subscribe_button.setText(format_votes(self.channel_info['votes']))

        self.window().channel_state_label.setText(self.channel_info["state"])
        self.window().subscription_widget.initialize_with_channel(self.channel_info)

    def _on_query_complete(self, data):
        self.window().channel_num_torrents_label.setText(
            "{}/{} torrents".format(data['total'], self.channel_info['torrents']))

    def load_torrents(self):
        self.controller.model.reset()
        self.controller.perform_query(first=1, last=50)  # Load the first 50 torrents
