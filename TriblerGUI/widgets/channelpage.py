from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QWidget

from TriblerGUI.utilities import get_image_path


class ChannelPage(QWidget):
    """
    The ChannelPage displays a list of a channel's contents.
    """

    def __init__(self):
        QWidget.__init__(self)
        self.channel_info = None

    def initialize_with_channel(self, channel_info):
        self.channel_info = channel_info
        self.window().channel_page_container.initialize_model(channel_id=channel_info['public_key'])

        container = self.window().channel_page_container
        container.torrents_table.setColumnHidden(container.model.column_position[u'commit_status'], True)
        container.torrents_table.setColumnHidden(container.model.column_position[u'subscribed'], True)
        container.buttons_container.setHidden(True)

        if len(channel_info['public_key']) == 40:
            container.top_bar_container.setHidden(True)
        else:
            container.top_bar_container.setHidden(False)
            container.dirty_channel_bar.setHidden(True)

        self.window().channel_preview_label.setHidden(int(channel_info['subscribed']) == 1)
        self.window().channel_back_button.setIcon(QIcon(get_image_path('page_back.png')))

        # initialize the page about a channel
        self.window().channel_name_label.setText(channel_info['name'])
        self.window().num_subs_label.setText(str(channel_info['votes']))
        self.window().subscription_widget.initialize_with_channel(channel_info)
