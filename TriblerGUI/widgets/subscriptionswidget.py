import json

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtWidgets import QWidget

from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.utilities import get_image_path


class SubscriptionsWidget(QWidget):
    """
    This widget shows a favorite button and the number of subscriptions that a specific channel has.
    """

    unsubscribed_channel = pyqtSignal(object)
    subscribed_channel = pyqtSignal(object)

    def __init__(self, parent):
        QWidget.__init__(self, parent)

        self.subscribe_button = None
        self.channel_info = None
        self.num_subs_label = None
        self.credit_mining_button = None
        self.request_mgr = None
        self.initialized = False

    def initialize_with_channel(self, channel):
        self.channel_info = channel
        if not self.initialized:
            self.subscribe_button = self.findChild(QWidget, "subscribe_button")
            self.num_subs_label = self.findChild(QWidget, "num_subs_label")
            self.credit_mining_button = self.findChild(QWidget, "credit_mining_button")

            self.subscribe_button.clicked.connect(self.on_subscribe_button_click)
            self.credit_mining_button.clicked.connect(self.on_credit_mining_button_click)
            self.initialized = True

        self.update_subscribe_button()

    def update_subscribe_button(self, remote_response=None):
        if remote_response and 'subscribed' in remote_response:
            self.channel_info["subscribed"] = remote_response['subscribed']

        if remote_response and 'votes' in remote_response:
            self.channel_info["votes"] = remote_response['votes']

        if self.channel_info["subscribed"]:
            self.subscribe_button.setIcon(QIcon(QPixmap(get_image_path('subscribed_yes.png'))))
        else:
            self.subscribe_button.setIcon(QIcon(QPixmap(get_image_path('subscribed_not.png'))))

        self.num_subs_label.setText(str(self.channel_info["votes"]))

        if self.window().tribler_settings:  # It could be that the settings are not loaded yet
            self.credit_mining_button.setHidden(not self.window().tribler_settings["credit_mining"]["enabled"])
            if self.channel_info["dispersy_cid"] in self.window().tribler_settings["credit_mining"]["sources"]:
                self.credit_mining_button.setIcon(QIcon(QPixmap(get_image_path('credit_mining_yes.png'))))
            else:
                self.credit_mining_button.setIcon(QIcon(QPixmap(get_image_path('credit_mining_not.png'))))
        else:
            self.credit_mining_button.hide()

    def on_subscribe_button_click(self):
        self.request_mgr = TriblerRequestManager()
        if self.channel_info["subscribed"]:
            self.request_mgr.perform_request("channels/subscribed/%s" %
                                             self.channel_info['dispersy_cid'],
                                             self.on_channel_unsubscribed, method='DELETE')
        else:
            self.request_mgr.perform_request("channels/subscribed/%s" %
                                             self.channel_info['dispersy_cid'],
                                             self.on_channel_subscribed, method='PUT')

    def on_channel_unsubscribed(self, json_result):
        if not json_result or not self:
            return
        if json_result["unsubscribed"]:
            self.unsubscribed_channel.emit(self.channel_info)
            self.channel_info["subscribed"] = False
            self.channel_info["votes"] -= 1
            self.update_subscribe_button()

    def on_channel_subscribed(self, json_result):
        if not json_result or not self:
            return
        if json_result["subscribed"]:
            self.subscribed_channel.emit(self.channel_info)
            self.channel_info["subscribed"] = True
            self.channel_info["votes"] += 1
            self.update_subscribe_button()

    def on_credit_mining_button_click(self):
        old_sources = self.window().tribler_settings["credit_mining"]["sources"]
        new_sources = [] if self.channel_info["dispersy_cid"] in old_sources else [self.channel_info["dispersy_cid"]]
        settings = {"credit_mining": {"sources": new_sources}}

        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("settings", self.on_credit_mining_sources,
                                         method='POST', data=json.dumps(settings))

    def on_credit_mining_sources(self, json_result):
        if not json_result:
            return
        if json_result["modified"]:
            old_source = next(iter(self.window().tribler_settings["credit_mining"]["sources"]), None)

            new_sources = [self.channel_info["dispersy_cid"]] if self.channel_info["dispersy_cid"] != old_source else []
            self.window().tribler_settings["credit_mining"]["sources"] = new_sources

            self.update_subscribe_button()

            channels_list = self.window().discovered_channels_list
            for index, data_item in enumerate(channels_list.data_items):
                if data_item[1]['dispersy_cid'] == old_source:
                    channel_item = channels_list.itemWidget(channels_list.item(index))
                    if channel_item:
                        channel_item.subscriptions_widget.update_subscribe_button()
                    break
