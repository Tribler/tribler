# coding=utf-8
from PyQt5 import uic
from PyQt5.QtCore import QTimer, QPropertyAnimation
from PyQt5.QtWidgets import QWidget, QGraphicsOpacityEffect


class ChannelListItem(QWidget):
    def __init__(self, parent, channel, fade_delay=0, should_fade=False):
        super(QWidget, self).__init__(parent)

        uic.loadUi('qt_resources/channel_list_item.ui', self)

        self.channel_name.setText(channel["name"])
        self.channel_description_label.setText("Active 6 days ago • %d items" % channel["torrents"])
        self.channel_num_subs_label.setText(str(channel["votes"]))
        if channel["sub"]:
            self.channel_subscribe_button.setText("✓ subscribed")
        else:
            self.channel_subscribe_button.setText("subscribe")

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
