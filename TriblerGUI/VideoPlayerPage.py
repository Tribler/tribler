import sys

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QPixmap, QIcon
from PyQt5.QtWidgets import QWidget, QFrame, QToolButton, QSlider

from TriblerGUI import vlc


class VideoPlayerPage(QWidget):

    def initialize_player(self):
        self.instance = vlc.Instance()
        self.mediaplayer = self.instance.media_player_new()
        self.video_player_widget = self.findChild(QWidget, "video_player_widget")
        self.video_player_position_slider = self.findChild(QSlider, "video_player_position_slider")
        self.video_player_volume_slider = self.findChild(QSlider, "video_player_volume_slider")
        self.video_player_volume_slider.valueChanged.connect(self.on_volume_change)
        self.video_player_volume_slider.setValue(self.mediaplayer.audio_get_volume())
        self.video_player_volume_slider.setFixedWidth(0)

        self.play_pause_button = self.findChild(QToolButton, "video_player_play_pause_button")
        self.play_pause_button.clicked.connect(self.on_play_pause_button_click)
        self.volume_button = self.findChild(QToolButton, "video_player_volume_button")
        self.volume_button.clicked.connect(self.on_volume_button_click)

        # Create play/pause and volume button images
        self.play_icon = QIcon(QPixmap("images/play.png"))
        self.pause_icon = QIcon(QPixmap("images/pause.png"))
        self.volume_on_icon = QIcon(QPixmap("images/volume_on.png"))
        self.volume_off_icon = QIcon(QPixmap("images/volume_off.png"))
        self.play_pause_button.setIcon(self.play_icon)
        self.volume_button.setIcon(self.volume_on_icon)

        if sys.platform.startswith('linux'): # for Linux using the X Server
            self.mediaplayer.set_xwindow(self.video_player_widget.winId())
        elif sys.platform == "win32": # for Windows
            self.mediaplayer.set_hwnd(self.video_player_widget.winId())
        elif sys.platform == "darwin": # for MacOS
            self.mediaplayer.set_nsobject(int(self.video_player_widget.winId()))

        self.manager = self.mediaplayer.event_manager()
        self.manager.event_attach(vlc.EventType.MediaPlayerPositionChanged, self.vlc_position_changed)

        # TODO martijn: temporarily set media hardcoded
        # filename = unicode("http://qthttp.apple.com.edgesuite.net/1010qwoeiuryfg/sl.m3u8")
        filename = unicode("http://127.0.0.1:7917/8a8898c4f65a2812006e24f34c314ecab74f6b44/3")
        self.media = self.instance.media_new(filename)
        self.mediaplayer.set_media(self.media)
        self.media.parse()

    def vlc_position_changed(self, data):
        self.video_player_position_slider.setValue(self.mediaplayer.get_position() * 1000)

    def on_play_pause_button_click(self):
        if not self.mediaplayer.is_playing():
            self.play_pause_button.setIcon(self.pause_icon)
            self.mediaplayer.play()
        else:
            self.play_pause_button.setIcon(self.play_icon)
            self.mediaplayer.pause()

    def on_volume_button_click(self):
        if not self.mediaplayer.audio_get_mute():
            self.volume_button.setIcon(self.volume_off_icon)
        else:
            self.volume_button.setIcon(self.volume_on_icon)
        self.mediaplayer.audio_toggle_mute()

    def on_volume_change(self):
        self.mediaplayer.audio_set_volume(self.video_player_volume_slider.value())
