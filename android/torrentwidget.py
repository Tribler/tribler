from kivy.uix.boxlayout import BoxLayout
from kivy.logger import Logger
import globalvars

from jnius import autoclass
Intent = autoclass('android.content.Intent')
Uri = autoclass('android.net.Uri')
PythonActivity = autoclass('org.renpy.android.PythonActivity')

"""
A widget for torrents so that they can be downloaded or streamed.
"""
class TorrentWidget(BoxLayout):
    torrent = None
    name = "Unknown"

    def set_torrent(self, torrent):
        self.torrent = torrent
        self.ids.filebutton.text = self.name = self.torrent.name

    def pressed(self):
        """
        Called when this widget is pressed.
        :return: Nothing.
        """
        Logger.info('Pressed TorrentWidget (should now take them to more info from where they can still choose to download or stream).') # TODO

    def start_stream(self):
        Logger.info('Starting download for stream in TorrentWidget.')
        download_mgr = globalvars.skelly.tw.get_download_mgr()
        download_mgr.subscribe_for_changed_progress_info(self._start_stream_callback)
        self.start_download()
        # TODO: take user to show progress screen, whoch is updated by _start_stream_callback

    def _start_stream_callback(self, info_hash):
        if info_hash != self.torrent.infohash:
            return
        download_mgr = globalvars.skelly.tw.get_download_mgr()
        progress_dict = download_mgr.get_progress(self.torrent.infohash)
        if progress_dict['vod_playable']:
            Logger.info('Starting video player.')
            self._start_external_android_player()
        else:

            # When metadata etc. has been downloaded then start downloading the actual video content in vod mode:
            status_code = progress_dict['status']
            if 3 <= status_code <= 5:
                Logger.info('Starting VOD mode.')
                self.vod_uri = download_mgr.start_vod(self.torrent.infohash)

    def _start_external_android_player(self):
        """
        Start the action chooser intent for viewing a video.
        :return: Nothing.
        """
        intent = Intent(Intent.ACTION_VIEW)
        intent.setDataAndType(Uri.parse(self.vod_uri), "video/*")
        PythonActivity.mActivity.startActivity(Intent.createChooser(intent, "Complete action using"))

    def start_download(self):
        Logger.info('Start download in TorrentWidget.')
        download_mgr = globalvars.skelly.tw.get_download_mgr()
        download_mgr.add_torrent(self.torrent.infohash, self.torrent.name)
        # TODO: navigate user to screen with downloaded torrents and show this torrent with a progress bar


