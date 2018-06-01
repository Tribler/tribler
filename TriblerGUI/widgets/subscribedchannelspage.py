from PyQt5.QtWidgets import QWidget

from TriblerGUI.widgets.channel_list_item import ChannelListItem
from TriblerGUI.defs import BUTTON_TYPE_NORMAL, BUTTON_TYPE_CONFIRM
from TriblerGUI.dialogs.confirmationdialog import ConfirmationDialog
from TriblerGUI.widgets.loading_list_item import LoadingListItem
from TriblerGUI.tribler_request_manager import TriblerRequestManager


class SubscribedChannelsPage(QWidget):
    """
    This page shows all the channels that the user has subscribed to.
    """

    def __init__(self):
        QWidget.__init__(self)

        self.dialog = None
        self.request_mgr = None

    def initialize(self):
        self.window().add_subscription_button.clicked.connect(self.on_add_subscription_clicked)

    def load_subscribed_channels(self):
        self.window().subscribed_channels_list.set_data_items([(LoadingListItem, None)])

        self.request_mgr = TriblerRequestManager()
        self.request_mgr.perform_request("channels/subscribed", self.received_subscribed_channels)

    def received_subscribed_channels(self, results):
        self.window().subscribed_channels_list.set_data_items([])
        items = []

        if len(results['subscribed']) == 0:
            self.window().subscribed_channels_list.set_data_items(
                [(LoadingListItem, "You are not subscribed to any channel.")])
            return

        for result in results['subscribed']:
            items.append((ChannelListItem, result))
        self.window().subscribed_channels_list.set_data_items(items)

    def on_add_subscription_clicked(self):
        self.dialog = ConfirmationDialog(self, "Add subscribed channel",
                                         "Please enter the identifier of the channel you want to subscribe to below. "
                                         "It can take up to a minute before the channel is visible in your list of "
                                         "subscribed channels.",
                                         [('ADD', BUTTON_TYPE_NORMAL), ('CANCEL', BUTTON_TYPE_CONFIRM)],
                                         show_input=True)
        self.dialog.dialog_widget.dialog_input.setPlaceholderText('Channel identifier')
        self.dialog.button_clicked.connect(self.on_subscription_added)
        self.dialog.show()

    def on_subscription_added(self, action):
        if action == 0:
            self.request_mgr = TriblerRequestManager()
            self.request_mgr.perform_request("channels/subscribed/%s" % self.dialog.dialog_widget.dialog_input.text(),
                                             self.on_channel_subscribed, method='PUT')

        self.dialog.close_dialog()
        self.dialog = None

    def on_channel_subscribed(self, _):
        pass
