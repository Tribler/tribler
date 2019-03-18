from __future__ import absolute_import

from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QWidget

from TriblerGUI.utilities import get_gui_setting, get_image_path
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
        self.gui_settings = None

    def initialize_channel_page(self, gui_settings):
        self.gui_settings = gui_settings
        self.model = TorrentsContentModel(hide_xxx=get_gui_setting(self.gui_settings, "family_filter", True,
                                                                   is_bool=True) if self.gui_settings else True)
        self.window().core_manager.events_manager.torrent_info_updated.connect(self.model.update_torrent_info)
        self.controller = TorrentsTableViewController(self.model,
                                                      self.window().channel_page_container.content_table,
                                                      self.window().channel_page_container.details_container,
                                                      None, self.window().channel_torrents_filter_input)

        # Remove the commit control from the delegate for performance
        commit_control = self.window().channel_page_container.content_table.delegate.commit_control
        self.window().channel_page_container.content_table.delegate.controls.remove(commit_control)

    def initialize_with_channel(self, channel_info):
        self.channel_info = channel_info

        self.window().channel_preview_label.setHidden(channel_info['subscribed'])
        self.window().channel_back_button.setIcon(QIcon(get_image_path('page_back.png')))
        self.window().channel_page_container.content_table.setFocus()

        # initialize the page about a channel
        self.window().channel_name_label.setText(channel_info['name'])
        self.window().num_subs_label.setText(str(channel_info['votes']))
        self.window().subscription_widget.initialize_with_channel(channel_info)
        self.window().channel_page_container.details_container.hide()

        self.model.channel_pk = channel_info['public_key']
        self.window().channel_torrents_filter_input.setText("")
        self.load_torrents()

    def load_torrents(self):
        self.controller.model.reset()
        self.controller.perform_query(first=1, last=50)  # Load the first 50 torrents
