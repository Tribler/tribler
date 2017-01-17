from PyQt5.QtWidgets import QWidget
from TriblerGUI.tribler_window import fc_channel_list_item


class ChannelListItem(QWidget, fc_channel_list_item):
    """
    This class is responsible for managing the item in the list of channels.
    The list item supports a fade-in effect, which can be enabled with the should_fade parameter in the constructor.
    """

    def __init__(self, parent, channel):
        QWidget.__init__(self, parent)
        fc_channel_list_item.__init__(self)

        self.setupUi(self)

        self.channel_info = channel
        self.channel_name.setText(channel["name"])
        self.channel_description_label.setText("%d items" % channel["torrents"])

        self.subscriptions_widget.initialize_with_channel(channel)
