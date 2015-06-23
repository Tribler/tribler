from kivy.uix.boxlayout import BoxLayout

"""
A widget for torrents so that they can be downloaded or streamed.
"""
class TorrentWidget(BoxLayout):
    name = "Unknown"

    def set_name(self, nom):
        self.name = nom
        self.ids.filebutton.text = nom

    def pressed(self):
        """
        Called when this widget is pressed.
        :return: Nothing.
        """
        print 'Pressed TorrentWidget'

    def start_stream(self):
        print 'Pressed TorrentWidget start stream'

    def start_download(self):
        print 'Pressed TorrentWidget start download'

