import os
import sys

from PyQt5.QtCore import QTimer, QEvent, Qt
from PyQt5.QtGui import QPixmap, QIcon
from PyQt5.QtWidgets import QWidget

from TriblerGUI.dialogs.confirmationdialog import ConfirmationDialog
from TriblerGUI.utilities import is_video_file, seconds_to_string, get_image_path


class VideoPlayerPage(QWidget):
    """
    This class manages the video player and all controls on the page.
    """

    def __init__(self):
        QWidget.__init__(self)

        self.video_player_port = None
        self.active_infohash = ""
        self.active_index = -1
        self.media = None
        self.mediaplayer = None
        self.instance = None
        self.manager = None
        self.play_icon = None
        self.pause_icon = None
        self.volume_on_icon = None
        self.volume_off_icon = None
        self.update_timer = None

    def initialize_player(self):
        vlc_available = True
        vlc = None
        try:
            from TriblerGUI import vlc
        except OSError:
            vlc_available = False

        if vlc and vlc.plugin_path:
            os.environ['VLC_PLUGIN_PATH'] = vlc.plugin_path

        if not vlc_available:
            # VLC is not available, we hide the video player button
            self.window().vlc_available = False
            self.window().left_menu_button_video_player.setHidden(True)
            return

        self.instance = vlc.Instance()
        self.mediaplayer = self.instance.media_player_new()
        self.window().video_player_widget.should_hide_video_widgets.connect(self.hide_video_widgets)
        self.window().video_player_widget.should_show_video_widgets.connect(self.show_video_widgets)
        self.window().video_player_position_slider.should_change_video_position.connect(
            self.on_should_change_video_time)
        self.window().video_player_volume_slider.valueChanged.connect(self.on_volume_change)
        self.window().video_player_volume_slider.setValue(self.mediaplayer.audio_get_volume())
        self.window().video_player_volume_slider.setFixedWidth(0)

        self.window().video_player_play_pause_button.clicked.connect(self.on_play_pause_button_click)
        self.window().video_player_volume_button.clicked.connect(self.on_volume_button_click)
        self.window().video_player_full_screen_button.clicked.connect(self.on_full_screen_button_click)

        # Create play/pause and volume button images
        self.play_icon = QIcon(QPixmap(get_image_path("play.png")))
        self.pause_icon = QIcon(QPixmap(get_image_path("pause.png")))
        self.volume_on_icon = QIcon(QPixmap(get_image_path("volume_on.png")))
        self.volume_off_icon = QIcon(QPixmap(get_image_path("volume_off.png")))
        self.window().video_player_play_pause_button.setIcon(self.play_icon)
        self.window().video_player_volume_button.setIcon(self.volume_on_icon)
        self.window().video_player_full_screen_button.setIcon(QIcon(QPixmap(get_image_path("full_screen.png"))))
        self.window().video_player_info_button.setIcon(QIcon(QPixmap(get_image_path("info.png"))))
        self.window().video_player_info_button.hide()

        if sys.platform.startswith('linux'):
            self.mediaplayer.set_xwindow(self.window().video_player_widget.winId())
        elif sys.platform == "win32":
            self.mediaplayer.set_hwnd(self.window().video_player_widget.winId())
        elif sys.platform == "darwin":
            self.mediaplayer.set_nsobject(int(self.window().video_player_widget.winId()))

        self.manager = self.mediaplayer.event_manager()
        self.manager.event_attach(vlc.EventType.MediaPlayerBuffering, self.on_vlc_player_buffering)
        self.manager.event_attach(vlc.EventType.MediaPlayerPlaying, self.on_vlc_player_playing)

        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.on_update_timer_tick)
        self.update_timer.start(500)

        self.window().left_menu_playlist.playing_item_change.connect(self.change_playing_index)
        self.window().left_menu_playlist.item_should_play.connect(self.on_play_pause_button_click)
        self.window().left_menu_playlist.list_loaded.connect(self.on_files_list_loaded)
        self.window().video_player_play_pause_button.setEnabled(False)

    def hide_video_widgets(self):
        if self.window().windowState() & Qt.WindowFullScreen:
            self.window().video_player_header_label.setHidden(True)
            self.window().video_player_controls_container.setHidden(True)

    def show_video_widgets(self):
        self.window().video_player_header_label.setHidden(False)
        self.window().video_player_controls_container.setHidden(False)

    def on_update_timer_tick(self):
        total_duration_str = "-:--"
        if self.media and self.media.get_duration() != 0:
            total_duration_str = seconds_to_string(self.media.get_duration() / 1000)

        if self.active_infohash == "" or self.active_index == -1:
            self.window().video_player_position_slider.setValue(0)
            self.window().video_player_time_label.setText("0:00 / -:--")
        else:
            video_time = self.mediaplayer.get_time()
            if video_time == -1:
                video_time = 0

            self.window().video_player_position_slider.setValue(self.mediaplayer.get_position() * 1000)
            self.window().video_player_time_label.setText("%s / %s" %
                                                          (seconds_to_string(video_time / 1000), total_duration_str))

    def update_with_download_info(self, download):
        self.window().video_player_info_button.popup.update(download)

    def on_vlc_player_buffering(self, event):
        pass

    def on_vlc_player_playing(self, event):
        pass

    def on_should_change_video_time(self, position):
        self.mediaplayer.set_position(position)

    def on_play_pause_button_click(self):
        if not self.active_infohash or self.active_index == -1:
            return

        if not self.mediaplayer.is_playing():
            self.window().video_player_play_pause_button.setIcon(self.pause_icon)
            self.mediaplayer.play()
        else:
            self.window().video_player_play_pause_button.setIcon(self.play_icon)
            self.mediaplayer.pause()

    def on_files_list_loaded(self):
        if self.active_index == -1:
            largest_index, largest_file = self.window().left_menu_playlist.get_largest_file()

            if not largest_file:
                # We don't have a media file in this torrent. Reset everything and show an error
                ConfirmationDialog.show_error(self.window(), "No media files", "This download contains no media files.")
                self.window().hide_left_menu_playlist()
                return

            self.active_index = largest_index
        self.play_active_item()

    def on_volume_button_click(self):
        if not self.mediaplayer.audio_get_mute():
            self.window().video_player_volume_button.setIcon(self.volume_off_icon)
        else:
            self.window().video_player_volume_button.setIcon(self.volume_on_icon)
        self.mediaplayer.audio_toggle_mute()

    def on_volume_change(self):
        self.mediaplayer.audio_set_volume(self.window().video_player_volume_slider.value())

    def on_full_screen_button_click(self):
        if not self.window().windowState() & Qt.WindowFullScreen:
            self.window().top_bar.hide()
            self.window().left_menu.hide()
            self.window().showFullScreen()
        else:
            self.window().exit_full_screen()

    def play_active_item(self):
        self.window().left_menu_playlist.set_active_index(self.active_index)
        file_info = self.window().left_menu_playlist.get_file_info(self.active_index)
        file_index = file_info["index"]

        self.window().video_player_header_label.setText(file_info["name"] if file_info else 'Unknown')

        # reset video player controls
        self.mediaplayer.stop()
        self.window().video_player_play_pause_button.setIcon(self.play_icon)
        self.window().video_player_position_slider.setValue(0)

        media_filename = u"http://127.0.0.1:" + unicode(self.video_player_port) + "/" + \
                         self.active_infohash + "/" + unicode(file_index)
        self.media = self.instance.media_new(media_filename)
        self.mediaplayer.set_media(self.media)
        self.media.parse()

        self.window().video_player_play_pause_button.setIcon(self.pause_icon)
        self.mediaplayer.play()

        self.window().video_player_play_pause_button.setEnabled(True)
        self.window().video_player_info_button.show()

    def play_media_item(self, infohash, menu_index):
        """
        Play a specific media item in a torrent. If the index is -1, we play the item with the largest size.
        """
        if infohash == self.active_infohash and menu_index == self.active_index:
            return  # We're already playing this item

        self.active_index = menu_index

        if infohash == self.active_infohash:
            # We changed the index of a torrent that is already playing
            if self.window().left_menu_playlist.loaded_list:
                self.play_active_item()
        else:
            # The download changed, reload the list
            self.window().left_menu_playlist.load_list(infohash)

        self.active_infohash = infohash

    def change_playing_index(self, index):
        self.play_media_item(self.active_infohash, index)

    def reset_player(self):
        """
        Reset the video player, i.e. when a download is removed that was being played.
        """
        self.active_infohash = ""
        self.active_index = -1
        self.window().left_menu_playlist.clear()
        self.window().video_player_header_label.setText("")
        self.mediaplayer.stop()
        self.mediaplayer.set_media(None)
        self.media = None
        self.window().video_player_play_pause_button.setIcon(self.play_icon)
        self.window().video_player_play_pause_button.setEnabled(False)
        self.window().video_player_position_slider.setValue(0)
        self.window().video_player_info_button.hide()

    def eventFilter(self, source, event):
        if event.type() == QEvent.KeyRelease and self.isVisible() and not self.window().top_search_bar.hasFocus() and\
                event.key() == Qt.Key_Space:
            self.on_play_pause_button_click()
        return QWidget.eventFilter(self, source, event)
