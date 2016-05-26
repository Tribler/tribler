from PyQt5.QtWidgets import QWidget
from TriblerGUI.channel_list_item import ChannelListItem
from TriblerGUI.defs import BUTTON_TYPE_NORMAL, BUTTON_TYPE_CONFIRM
from TriblerGUI.dialogs.confirmationdialog import ConfirmationDialog
from TriblerGUI.tribler_request_manager import TriblerRequestManager


class SubscribedChannelsPage(QWidget):

    def initialize(self):
        self.window().add_subscription_button.clicked.connect(self.on_add_subscription_clicked)

    def load_subscribed_channels(self):
        self.subscribed_channels_request_manager = TriblerRequestManager()
        self.subscribed_channels_request_manager.perform_request("channels/subscribed",
                                                                 self.received_subscribed_channels)

    def received_subscribed_channels(self, results):
        items = []
        for result in results['subscribed']:
            items.append((ChannelListItem, result))
        self.window().subscribed_channels_list.set_data_items(items)

    def on_add_subscription_clicked(self):
        self.dialog = ConfirmationDialog(self, "Add subscribed channel", "Please enter the identifier of the channel you want to subscribe to below. It can take up to a minute before the channel is visible in your list of subscribed channels.", [('add', BUTTON_TYPE_NORMAL), ('cancel', BUTTON_TYPE_CONFIRM)], show_input=True)
        self.dialog.dialog_widget.dialog_input.setPlaceholderText('Channel identifier')
        self.dialog.button_clicked.connect(self.on_subscription_added)
        self.dialog.show()

    def on_subscription_added(self, action):
        if action == 0:
            # TODO
            pass
        self.dialog.setParent(None)
        self.dialog = None
