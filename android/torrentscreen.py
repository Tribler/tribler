from kivy.uix.boxlayout import BoxLayout
from kivy.logger import Logger
from kivy.uix.screenmanager import Screen
import globalvars

from jnius import autoclass
Intent = autoclass('android.content.Intent')
Uri = autoclass('android.net.Uri')
PythonActivity = autoclass('org.renpy.android.PythonActivity')

"""
A widget for torrents that takes users to the torrent info screen when pressed.
"""
class TorrentWidget(BoxLayout):
    torrent = None
    name = "Unknown"

    def set_torrent(self, torrent):
        self.torrent = torrent
        self.ids.filebutton.text = self.name = self.torrent.name

    def on_press(self):
        main = globalvars.skelly
        main.TorrentInfoScr.torrent = self.torrent
        main.swap_to(main.TorrentInfoScr)

"""
The screen shown when a torrent is pressed. Here the user can select to download or stream a torrent.
"""
class TorrentInfoScreen(Screen):
    torrent = None

    def start_download(self):
        Logger.info('Start download in TorrentInfoScreen.')
        download_mgr = globalvars.skelly.tw.get_download_mgr()
        download_mgr.add_torrent(self.torrent.infohash, self.torrent.name)
        # TODO: navigate user to screen with downloaded torrents and show this torrent with a progress bar

    def start_stream(self):
        Logger.info('Starting download for stream in TorrentInfoScreen.')
        download_mgr = globalvars.skelly.tw.get_download_mgr()
        download_mgr.subscribe_for_changed_progress_info(self._start_stream_callback)
        self.start_download()
        # TODO: Show progress to user, which is updated by _start_stream_callback

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

