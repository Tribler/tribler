# coding=utf-8
from PyQt5 import uic
from PyQt5.QtCore import QTimer, QPropertyAnimation
from PyQt5.QtWidgets import QWidget, QGraphicsOpacityEffect
from TriblerGUI.tribler_request_manager import TriblerRequestManager


class ChannelListItem(QWidget):
    """
    This class is responsible for managing the item in the list of channels.
    The list item supports a fade-in effect, which can be enabled with the should_fade parameter in the constructor.
    """

    def __init__(self, parent, channel, fade_delay=0, should_fade=False):
        super(QWidget, self).__init__(parent)

        uic.loadUi('qt_resources/channel_list_item.ui', self)

        self.channel_info = channel
        self.channel_name.setText(channel["name"])
        self.channel_description_label.setText("Active 6 days ago • %d items" % channel["torrents"])
        self.channel_subscribe_button.clicked.connect(self.on_channel_subscribe_button_click)

        self.update_subscribe_button()

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

    def update_subscribe_button(self):
        if self.channel_info["subscribed"]:
            self.channel_subscribe_button.setText("✓ subscribed")
        else:
            self.channel_subscribe_button.setText("subscribe")

        self.channel_num_subs_label.setText(str(self.channel_info["votes"]))

    def on_channel_subscribe_button_click(self):
        self.request_mgr = TriblerRequestManager()
        if self.channel_info["subscribed"]:
            self.request_mgr.perform_request("channels/subscribed/%s" % self.channel_info['dispersy_cid'], self.on_channel_unsubscribed, method='DELETE')
        else:
            self.request_mgr.perform_request("channels/subscribed/%s" % self.channel_info['dispersy_cid'], self.on_channel_subscribed, method='PUT')

    def on_channel_unsubscribed(self, json_result):
        if json_result["unsubscribed"]:
            self.channel_info["subscribed"] = False
            self.channel_info["votes"] -= 1
            self.update_subscribe_button()

    def on_channel_subscribed(self, json_result):
        if json_result["subscribed"]:
            self.channel_info["subscribed"] = True
            self.channel_info["votes"] += 1
            self.update_subscribe_button()
