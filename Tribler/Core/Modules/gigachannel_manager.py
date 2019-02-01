import os
from binascii import hexlify

from pony.orm import db_session
from twisted.internet.defer import Deferred
from twisted.internet.task import LoopingCall

from Tribler.Core.DownloadConfig import DownloadStartupConfig
from Tribler.Core.Modules.MetadataStore.OrmBindings.channel_node import COMMITTED
from Tribler.Core.TorrentDef import TorrentDefNoMetainfo, TorrentDef
from Tribler.Core.simpledefs import DLSTATUS_SEEDING
from Tribler.pyipv8.ipv8.taskmanager import TaskManager


class GigaChannelManager(TaskManager):
    """
    This class represents the main manager for gigachannels.
    It provides methods to manage channels, download new channels or remove existing ones.
    """

    def __init__(self, session):
        super(GigaChannelManager, self).__init__()
        self.session = session

    def start(self):
        """
        The Metadata Store checks the database at regular intervals to see if new channels are available for preview
        or subscribed channels require updating.
        """
        self.updated_my_channel()  # Just in case

        channels_check_interval = 5.0  # seconds
        self.register_task("Process channels download queue and remove cruft",
                           LoopingCall(self.service_channels)).start(channels_check_interval)

    def shutdown(self):
        """
        Stop the gigachannel manager.
        """
        self.shutdown_task_manager()

    def remove_cruft_channels(self):
        with db_session:
            channels, _ = self.session.lm.mds.ChannelMetadata.get_channels(last=10000, subscribed=True)
            subscribed_infohashes = [c.infohash for c in list(channels)]

        cruft_list = [d for d in self.session.lm.get_channel_downloads() \
                      if (d.infohash not in subscribed_infohashes)]
        self.remove_channels_downloads(cruft_list)

    def service_channels(self):
        try:
            self.remove_cruft_channels()
        except:
            pass
        try:
            self.check_channels_updates()
        except:
            pass


    def check_channels_updates(self):
        """
        Check whether there are channels that are updated. If so, download the new version of the channel.
        """
        # FIXME: These naughty try-except-pass workarounds are necessary to keep the loop going in all circumstances

        with db_session:
            channels_queue = list(self.session.lm.mds.ChannelMetadata.get_updated_channels())

        for channel in channels_queue:
            try:
                if not self.session.has_download(str(channel.infohash)):
                    self._logger.info("Downloading new channel version %s ver %i->%i",
                                      str(channel.public_key).encode("hex"),
                                      channel.local_version, channel.timestamp)
                    self.download_channel(channel)
            except:
                pass

    def on_channel_download_finished(self, download, channel_id, finished_deferred=None):
        """
        We have finished with downloading a channel.
        :param download: The channel download itself.
        :param channel_id: The ID of the channel.
        :param finished_deferred: An optional deferred that should fire if the channel download has finished.
        """
        if download.get_channel_download():
            channel_dirname = os.path.join(self.session.lm.mds.channels_dir, download.get_def().get_name())
            self.session.lm.mds.process_channel_dir(channel_dirname, channel_id)
            if finished_deferred:
                finished_deferred.callback(download)

    @db_session
    def remove_channel(self, channel):
        """
        Remove a channel from your local database/download list.
        :param channel: The channel to remove.
        """
        channel.subscribed = False
        channel.remove_contents()
        channel.local_version = 0

        # Remove all stuff matching the channel dir name / public key / torrent title
        remove_list = [d for d in self.session.lm.get_channel_downloads() if d.tdef.get_name_utf8() == channel.dir_name]
        self.remove_channels_downloads(remove_list)

    def remove_channels_downloads(self, remove_list):
        # FIXME: handle the case when a torrent for the old version of the channel overlaps the current version
        def _on_remove_failure(failure):
            self._logger.error("Error when removing the channel download: %s", failure)

        for i, d in enumerate(remove_list):
            deferred = self.session.remove_download(d, remove_content=True)
            deferred.addErrback(_on_remove_failure)
            self.register_task(u'remove_channel' + d.tdef.get_name_utf8() + u'-' + hexlify(d.tdef.get_infohash()) +
                               u'-' + str(i), deferred)

    def download_channel(self, channel):
        """
        Download a channel with a given infohash and title.
        :param channel: The channel metadata ORM object.
        """
        finished_deferred = Deferred()

        dcfg = DownloadStartupConfig()
        dcfg.set_dest_dir(self.session.lm.mds.channels_dir)
        dcfg.set_channel_download(True)
        tdef = TorrentDefNoMetainfo(infohash=str(channel.infohash), name=channel.dir_name)
        download = self.session.start_download_from_tdef(tdef, dcfg)
        channel_id = channel.public_key
        # TODO: add errbacks here!
        download.finished_callback = lambda dl: self.on_channel_download_finished(dl, channel_id, finished_deferred)
        if download.get_state().get_status() == DLSTATUS_SEEDING and not download.finished_callback_already_called:
            download.finished_callback_already_called = True
            download.finished_callback(download)
        return download, finished_deferred

    def updated_my_channel(self):
        """
        Notify the core that we updated our channel.
        """
        my_channel = self.session.lm.mds.ChannelMetadata.get_my_channel()
        if my_channel and my_channel.status == COMMITTED and \
                not self.session.has_download(str(my_channel.infohash)):
            torrent_path = os.path.join(self.session.lm.mds.channels_dir, my_channel.dir_name + ".torrent")
        else:
            return
        tdef = TorrentDef.load(torrent_path)
        dcfg = DownloadStartupConfig()
        dcfg.set_dest_dir(self.session.lm.mds.channels_dir)
        dcfg.set_channel_download(True)
        self.session.lm.add(tdef, dcfg)
