from __future__ import absolute_import
from PyQt5.QtWidgets import QWidget

from TriblerGUI.defs import BUTTON_TYPE_NORMAL, BUTTON_TYPE_CONFIRM
from TriblerGUI.dialogs.confirmationdialog import ConfirmationDialog
from TriblerGUI.tribler_request_manager import TriblerRequestManager
from TriblerGUI.widgets.lazytableview import ACTION_BUTTONS


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


        container = self.window().subscribed_channels_container
        container.initialize_model(subscribed=True)
        container.channel_entry_clicked.connect(self.window().on_channel_clicked)
        container.torrents_table.setColumnHidden(container.model.column_position[u'commit_status'], True)
        container.torrents_table.setColumnHidden(container.model.column_position[u'health'], True)
        container.torrents_table.setColumnHidden(container.model.column_position[ACTION_BUTTONS], True)
        container.buttons_container.setHidden(True)
        container.top_bar_container.setHidden(True)
        container.details_tab_widget.setHidden(True)

    def load_subscribed_channels(self):
        self.window().subscribed_channels_container.model.refresh()

    #FIXME: GigaChannel
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

    #FIXME: GigaChannel
    def on_subscription_added(self, action):
        if action == 0:
            self.request_mgr = TriblerRequestManager()
            self.request_mgr.perform_request("channels/subscribed/%s" % self.dialog.dialog_widget.dialog_input.text(),
                                             self.on_channel_subscribed, method='PUT')

        self.dialog.close_dialog()
        self.dialog = None

    def on_channel_subscribed(self, _):
        pass
