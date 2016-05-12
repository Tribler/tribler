import sys

from PyQt5.QtGui import QPixmap, QIcon
from PyQt5.QtWidgets import QWidget
from Tribler import vlc


class VideoPlayerPage(QWidget):
    """
    This class manages the video player and all controls on the page.
    """

    INFOHASH = u"8a8898c4f65a2812006e24f34c314ecab74f6b44" # TODO Martijn: for testing purposes
    ACTIVE_INDEX = -1

    def __init__(self):
        super(VideoPlayerPage, self).__init__()
        self.video_player_port = None

    def initialize_player(self):
        self.instance = vlc.Instance()
        self.mediaplayer = self.instance.media_player_new()
        self.window().video_player_position_slider.should_change_video_position.connect(self.on_should_change_video_time)
        self.window().video_player_volume_slider.valueChanged.connect(self.on_volume_change)
        self.window().video_player_volume_slider.setValue(self.mediaplayer.audio_get_volume())
        self.window().video_player_volume_slider.setFixedWidth(0)

        self.window().video_player_play_pause_button.clicked.connect(self.on_play_pause_button_click)
        self.window().video_player_volume_button.clicked.connect(self.on_volume_button_click)
        self.window().video_player_playlist_button.clicked.connect(self.on_playlist_button_click)
        self.window().video_player_files_menu.should_change_playing_file.connect(self.should_change_playing_file)
        self.window().video_player_files_menu.initialize_file_menu()
        self.window().video_player_files_menu.hide()

        # Create play/pause and volume button images
        self.play_icon = QIcon(QPixmap("images/play.png"))
        self.pause_icon = QIcon(QPixmap("images/pause.png"))
        self.menu_icon = QIcon(QPixmap("images/menu_white.png"))
        self.volume_on_icon = QIcon(QPixmap("images/volume_on.png"))
        self.volume_off_icon = QIcon(QPixmap("images/volume_off.png"))
        self.window().video_player_play_pause_button.setIcon(self.play_icon)
        self.window().video_player_volume_button.setIcon(self.volume_on_icon)
        self.window().video_player_playlist_button.setIcon(self.menu_icon)

        if sys.platform.startswith('linux'):
            self.mediaplayer.set_xwindow(self.window().video_player_widget.winId())
        elif sys.platform == "win32":
            self.mediaplayer.set_hwnd(self.window().video_player_widget.winId())
        elif sys.platform == "darwin":
            self.mediaplayer.set_nsobject(int(self.window().video_player_widget.winId()))

        self.manager = self.mediaplayer.event_manager()
        self.manager.event_attach(vlc.EventType.MediaPlayerPositionChanged, self.vlc_position_changed)
        self.manager.event_attach(vlc.EventType.MediaPlayerBuffering, self.on_vlc_player_buffering)
        self.manager.event_attach(vlc.EventType.MediaPlayerPlaying, self.on_vlc_player_playing)

    def on_vlc_player_buffering(self, event):
        print event

    def on_vlc_player_playing(self, event):
        print event

    def on_should_change_video_time(self, position):
        self.mediaplayer.set_position(position)

    def vlc_position_changed(self, data):
        self.video_player_position_slider.setValue(self.mediaplayer.get_position() * 1000)

    def on_play_pause_button_click(self):
        if not self.mediaplayer.is_playing():
            self.window().video_player_play_pause_button.setIcon(self.pause_icon)
            self.mediaplayer.play()
        else:
            self.window().video_player_play_pause_button.setIcon(self.play_icon)
            self.mediaplayer.pause()

    def on_volume_button_click(self):
        if not self.mediaplayer.audio_get_mute():
            self.window().video_player_volume_button.setIcon(self.volume_off_icon)
        else:
            self.window().video_player_volume_button.setIcon(self.volume_on_icon)
        self.mediaplayer.audio_toggle_mute()

    def on_volume_change(self):
        self.mediaplayer.audio_set_volume(self.window().video_player_volume_slider.value())

    def on_playlist_button_click(self):
        if self.video_player_files_menu.isHidden():
            self.video_player_files_menu.show()
            self.video_player_files_menu.load_download_files(self.INFOHASH)
        else:
            self.video_player_files_menu.hide()

    def should_change_playing_file(self, index):
        self.ACTIVE_INDEX = index

        # reset video player controls
        self.mediaplayer.stop()
        self.play_pause_button.setIcon(self.play_icon)
        self.video_player_position_slider.setValue(0)

        # TODO martijn: temporarily set media hardcoded
        #filename = u"http://qthttp.apple.com.edgesuite.net/1010qwoeiuryfg/sl.m3u8"
        filename = u"http://127.0.0.1:" + unicode(self.video_player_port) + "/" + self.INFOHASH + "/" + unicode(self.ACTIVE_INDEX)
        self.media = self.instance.media_new(filename)
        self.mediaplayer.set_media(self.media)
        self.media.parse()
