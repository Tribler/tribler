from urllib import quote_plus

import logging
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QWidget
from TriblerGUI.defs import STATUS_GOOD, STATUS_DEAD
from TriblerGUI.defs import STATUS_UNKNOWN

from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.tribler_window import fc_channel_torrent_list_item
from TriblerGUI.utilities import format_size, get_image_path, get_gui_setting


class ChannelTorrentListItem(QWidget, fc_channel_torrent_list_item):
    """
    This class is responsible for managing the item in the torrents list of a channel.
    """

    def __init__(self, parent, torrent, show_controls=False, on_remove_clicked=None):
        QWidget.__init__(self, parent)
        fc_channel_torrent_list_item.__init__(self)

        self.torrent_info = torrent
        self._logger = logging.getLogger('TriblerGUI')

        self.setupUi(self)
        self.show_controls = show_controls
        self.remove_control_button_container.setHidden(True)
        self.control_buttons_container.setHidden(True)
        self.is_health_checking = False
        self.has_health = False
        self.health_request_mgr = None
        self.request_mgr = None
        self.download_uri = None
        self.dialog = None

        self.channel_torrent_name.setText(torrent["name"])
        if torrent["size"] is None:
            self.channel_torrent_description.setText("Size: -")
        else:
            self.channel_torrent_description.setText("Size: %s" % format_size(float(torrent["size"])))

        if torrent["category"]:
            self.channel_torrent_category.setText(torrent["category"].lower())
        else:
            self.channel_torrent_category.setText("unknown")
        self.thumbnail_widget.initialize(torrent["name"], 24)

        if torrent["last_tracker_check"] > 0 or torrent["num_seeders"] and torrent["num_leechers"]:
            self.has_health = True
            self.update_health(int(torrent["num_seeders"]), int(torrent["num_leechers"]))

        self.torrent_play_button.clicked.connect(self.on_play_button_clicked)
        self.torrent_download_button.clicked.connect(self.on_download_clicked)
        self.torrent_check_button.clicked.connect(lambda: self.check_health(force=True))

        if not self.window().vlc_available:
            self.torrent_play_button.setHidden(True)

        if on_remove_clicked is not None:
            self.remove_torrent_button.clicked.connect(lambda: on_remove_clicked(self))

    def on_download_clicked(self):
        self.download_uri = (u"magnet:?xt=urn:btih:%s&dn=%s" %
                             (self.torrent_info["infohash"], self.torrent_info['name'])).encode('utf-8')
        self.window().start_download_from_uri(self.download_uri)

    def on_play_button_clicked(self):
        self.download_uri = (u"magnet:?xt=urn:btih:%s&dn=%s" %
                             (self.torrent_info["infohash"], self.torrent_info['name'])).encode('utf-8')

        self.window().perform_start_download_request(self.download_uri,
                                                     self.window().tribler_settings['download_defaults'][
                                                         'anonymity_enabled'],
                                                     self.window().tribler_settings['download_defaults'][
                                                         'safeseeding_enabled'],
                                                     self.window().tribler_settings['download_defaults']['saveas'],
                                                     [], 0, callback=self.on_play_request_done)

    def on_play_request_done(self, result):
        if not self:
            return
        self.window().left_menu_button_video_player.click()
        self.window().video_player_page.play_media_item(self.torrent_info["infohash"], -1)

    def show_buttons(self):
        if not self.show_controls:
            self.remove_control_button_container.setHidden(True)
            self.control_buttons_container.setHidden(False)
            self.torrent_play_button.setIcon(QIcon(get_image_path('play.png')))
            self.torrent_download_button.setIcon(QIcon(get_image_path('downloads.png')))
            self.torrent_check_button.setIcon(QIcon(get_image_path('history.png')))
        else:
            self.control_buttons_container.setHidden(True)
            self.remove_control_button_container.setHidden(False)
            self.remove_torrent_button.setIcon(QIcon(get_image_path('delete.png')))

    def hide_buttons(self):
        self.remove_control_button_container.setHidden(True)
        self.control_buttons_container.setHidden(True)

    def enterEvent(self, _):
        self.show_buttons()

    def leaveEvent(self, _):
        self.hide_buttons()

    def on_cancel_health_check(self):
        """
        The request for torrent health could not be queued.
        Go back to the intial state.
        """
        try:
            self.health_text.setText("unknown health")
            self.set_health_indicator(STATUS_UNKNOWN)
            self.is_health_checking = False
            self.has_health = False
        except RuntimeError:
            self._logger.error("The underlying GUI widget has already been removed.")

    def check_health(self, force=False):
        """
        Perform a request to check the health of the torrent that is represented by this widget.
        Don't do this if we are already checking the health or if we have the health info.
        """
        if (self.is_health_checking or self.has_health) and not force:  # Don't check health again
            return

        self.health_text.setText("checking health...")
        self.set_health_indicator(STATUS_UNKNOWN)
        self.is_health_checking = True
        self.health_request_mgr = TriblerRequestManager()
        self.health_request_mgr.perform_request("torrents/%s/health?timeout=15&refresh=%d" %
                                                (self.torrent_info["infohash"], 1 if force else 0),
                                                self.on_health_response, capture_errors=False, priority="LOW",
                                                on_cancel=self.on_cancel_health_check)

    def on_health_response(self, response):
        """
        When we receive a health response, update the health status.
        """
        if not self:  # The channel list item might have been deleted already (i.e. by doing another search).
            return

        self.has_health = True
        total_seeders = 0
        total_leechers = 0

        if not response or 'error' in response:
            self.update_health(0, 0)  # Just set the health to 0 seeders, 0 leechers
            return

        for _, status in response['health'].iteritems():
            if 'error' in status:
                continue  # Timeout or invalid status

            total_seeders += int(status['seeders'])
            total_leechers += int(status['leechers'])

        self.is_health_checking = False
        self.update_health(total_seeders, total_leechers)

    def update_health(self, seeders, leechers):
        try:
            if seeders > 0:
                self.health_text.setText("good health (S%d L%d)" % (seeders, leechers))
                self.set_health_indicator(STATUS_GOOD)
            elif leechers > 0:
                self.health_text.setText("unknown health (found peers)")
                self.set_health_indicator(STATUS_UNKNOWN)
            else:
                self.health_text.setText("no peers found")
                self.set_health_indicator(STATUS_DEAD)
        except RuntimeError:
            self._logger.error("The underlying GUI widget has already been removed.")

    def set_health_indicator(self, status):
        color = "orange"
        if status == STATUS_GOOD:
            color = "green"
        elif status == STATUS_UNKNOWN:
            color = "orange"
        elif status == STATUS_DEAD:
            color = "red"

        self.health_indicator.setStyleSheet("background-color: %s; border-radius: %dpx"
                                            % (color, self.health_indicator.height() / 2))
