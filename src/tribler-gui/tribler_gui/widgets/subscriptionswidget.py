import json

from PyQt5.QtWidgets import QWidget

import tribler_core.utilities.json_util as json

from tribler_gui.tribler_request_manager import TriblerNetworkRequest
from tribler_gui.utilities import format_votes


class SubscriptionsWidget(QWidget):
    """
    This widget shows a favorite button and the number of subscriptions that a specific channel has.
    """

    def __init__(self, parent):
        QWidget.__init__(self, parent)

        self.subscribe_button = None
        self.initialized = False
        self.contents_widget = None

    def initialize(self, contents_widget):
        if not self.initialized:
            # We supply a link to the parent channelcontentswidget to use its property that
            # returns the current model in use (top of the stack)
            self.contents_widget = contents_widget
            self.subscribe_button = self.findChild(QWidget, "subscribe_button")

            self.subscribe_button.clicked.connect(self.on_subscribe_button_click)
            self.initialized = True

    def update_subscribe_button(self, remote_response=None):
        if remote_response and "subscribed" in remote_response:
            self.contents_widget.model.channel_info["subscribed"] = remote_response["subscribed"]

        color = '#FE6D01' if int(self.contents_widget.model.channel_info["subscribed"]) else '#fff'
        self.subscribe_button.setStyleSheet('border:none; color: %s' % color)
        self.subscribe_button.setText(format_votes(self.contents_widget.model.channel_info['votes']))

        # Disable channel control buttons for LEGACY_ENTRY channels
        hide_controls = self.contents_widget.model.channel_info["status"] == 1000
        self.subscribe_button.setHidden(hide_controls)

    def on_subscribe_button_click(self):
        TriblerNetworkRequest(
            "metadata/%s/%i"
            % (self.contents_widget.model.channel_info[u'public_key'], self.contents_widget.model.channel_info[u'id']),
            lambda data: self.update_subscribe_button(remote_response=data),
            raw_data=json.dumps({"subscribed": int(not self.contents_widget.model.channel_info["subscribed"])}),
            method='PATCH',
        )
