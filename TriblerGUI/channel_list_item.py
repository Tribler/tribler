# coding=utf-8
from PyQt5.QtCore import QTimer, QPropertyAnimation
from PyQt5.QtWidgets import QWidget, QGraphicsOpacityEffect
from TriblerGUI.tribler_window import fc_channel_list_item


class ChannelListItem(QWidget, fc_channel_list_item):
    """
    This class is responsible for managing the item in the list of channels.
    The list item supports a fade-in effect, which can be enabled with the should_fade parameter in the constructor.
    """

    def __init__(self, parent, channel, fade_delay=0, should_fade=False):
        super(QWidget, self).__init__(parent)

        self.setupUi(self)

        self.channel_info = channel
        self.channel_name.setText(channel["name"])
        self.channel_description_label.setText("Active 6 days ago • %d items" % channel["torrents"])

        self.subscriptions_widget.initialize_with_channel(channel)

        if should_fade:
            self.opacity_effect = QGraphicsOpacityEffect(self)
            self.opacity_effect.setOpacity(0)
            self.setGraphicsEffect(self.opacity_effect)

            self.timer = QTimer()
            self.timer.setInterval(fade_delay)
            self.timer.timeout.connect(self.fadeIn)
            self.timer.start()

    def fadeIn(self):
        self.anim = QPropertyAnimation(self.opacity_effect, 'opacity')
        self.anim.setDuration(800)
        self.anim.setStartValue(0)
        self.anim.setEndValue(1)
        self.anim.start()
        self.timer.stop()
