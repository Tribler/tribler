from __future__ import absolute_import

import os
from binascii import hexlify

from ipv8.taskmanager import TaskManager

from pony.orm import db_session

from twisted.internet.task import LoopingCall
from twisted.internet.threads import deferToThread

from Tribler.Core.DownloadConfig import DownloadStartupConfig
from Tribler.Core.Modules.MetadataStore.OrmBindings.channel_node import COMMITTED
from Tribler.Core.TorrentDef import TorrentDef, TorrentDefNoMetainfo
from Tribler.Core.simpledefs import NTFY_CHANNEL_ENTITY, NTFY_UPDATE


class GigaChannelManager(TaskManager):
    """
    This class represents the main manager for gigachannels.
    It provides methods to manage channels, download new channels or remove existing ones.
    """

    def __init__(self, session):
        super(GigaChannelManager, self).__init__()
        self.session = session
        self.channels_lc = None

    def start(self):
        """
        The Metadata Store checks the database at regular intervals to see if new channels are available for preview
        or subscribed channels require updating.
        """

        # Test if we our channel is there, but we don't share it because Tribler was closed unexpectedly
        try:
            with db_session:
                my_channel = self.session.lm.mds.ChannelMetadata.get_my_channel()
            if my_channel and my_channel.status == COMMITTED and \
                    not self.session.has_download(str(my_channel.infohash)):
                torrent_path = os.path.join(self.session.lm.mds.channels_dir, my_channel.dir_name + ".torrent")
                self.updated_my_channel(TorrentDef.load(torrent_path))
        except Exception:
            self._logger.exception("Error when tried to resume personal channel seeding on GigaChannel Manager startup")

        channels_check_interval = 5.0  # seconds
        self.channels_lc = self.register_task("Process channels download queue and remove cruft",
                                              LoopingCall(self.service_channels)).start(channels_check_interval)

    def shutdown(self):
        """
        Stop the gigachannel manager.
        """
        self.shutdown_task_manager()

    def remove_cruft_channels(self):
        """
        Assembles a list of obsolete channel torrents to be removed.
        The list is formed from older versions of channels we are subscribed to and from channel torrents we are not
        subscribed to (i.e. we recently unsubscribed from these). The unsubscribed channels are removed completely
        with their contents, while in the case of older versions the files are left in place because the newer version
        possibly uses them.
        :return: list of tuples (download_to_remove=download, remove_files=Bool)
        """
        with db_session:
            channels, _ = self.session.lm.mds.ChannelMetadata.get_entries(last=10000, subscribed=True)
            subscribed_infohashes = [bytes(c.infohash) for c in list(channels)]
            dirnames = [c.dir_name for c in channels]

        # TODO: add some more advanced logic for removal of older channel versions
        cruft_list = [(d, d.get_def().get_name_utf8() not in dirnames)
                      for d in self.session.lm.get_channel_downloads()
                      if bytes(d.get_def().infohash) not in subscribed_infohashes]
        self.remove_channels_downloads(cruft_list)

    def service_channels(self):
        try:
            self.remove_cruft_channels()
        except Exception:
            self._logger.exception("Error when tried to check for cruft channels")
        try:
            self.check_channels_updates()
        except Exception:
            self._logger.exception("Error when checking for channel updates")

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
                                      hexlify(str(channel.public_key)),
                                      channel.local_version, channel.timestamp)
                    self.download_channel(channel)
            except Exception:
                self._logger.exception("Error when tried to download a newer version of channel %s",
                                       hexlify(channel.public_key))

    # TODO: finish this routine
    # This thing should check if the files in the torrent we're going to delete are used in another torrent for
    # the newer version of the same channel, and determine a safe sub-set to delete.
    """
    def safe_files_to_remove(self, download):
        # Check for intersection of files from old download with files from the newer version of the same channel
        dirname = download.get_def().get_name_utf8()
        files_to_remove = []
        with db_session:
            channel = self.session.lm.mds.ChannelMetadata.get_channel_with_dirname(dirname)
        if channel and channel.subscribed:
            print self.session.lm.downloads
            current_version = self.session.get_download(hexlify(channel.infohash))
            current_version_files = set(current_version.get_tdef().get_files())
            obsolete_version_files = set(download.get_tdef().get_files())
            files_to_remove_relative = obsolete_version_files - current_version_files
            for f in files_to_remove_relative:
                files_to_remove.append(os.path.join(dirname, f))
        return files_to_remove
    """

    def remove_channels_downloads(self, to_remove_list):
        """
        :param to_remove_list: list of tuples (download_to_remove=download, remove_files=Bool)
        """

        # TODO: make file removal from older versions safe (i.e. check if it overlaps with newer downloads)

        """
        files_to_remove = []
        for download in to_remove_list:
            files_to_remove.extend(self.safe_files_to_remove(download))
        """

        def _on_remove_failure(failure):
            self._logger.error("Error when removing the channel download: %s", failure)

        for i, dl_tuple in enumerate(to_remove_list):
            d, remove_content = dl_tuple
            deferred = self.session.remove_download(d, remove_content=remove_content)
            deferred.addErrback(_on_remove_failure)
            self.register_task(u'remove_channel' + d.tdef.get_name_utf8() + u'-' + hexlify(d.tdef.get_infohash()) +
                               u'-' + str(i), deferred)

        """
        def _on_torrents_removed(torrent):
            print files_to_remove
        dl = DeferredList(removed_list)
        dl.addCallback(_on_torrents_removed)
        self.register_task(u'remove_channels_files-' + "_".join([d.tdef.get_name_utf8() for d in to_remove_list]), dl)
        """

    def download_channel(self, channel):
        """
        Download a channel with a given infohash and title.
        :param channel: The channel metadata ORM object.
        """
        dcfg = DownloadStartupConfig(state_dir=self.session.config.get_state_dir())
        dcfg.set_dest_dir(self.session.lm.mds.channels_dir)
        dcfg.set_channel_download(True)
        tdef = TorrentDefNoMetainfo(infohash=str(channel.infohash), name=channel.dir_name)
        download = self.session.start_download_from_tdef(tdef, dcfg)

        def on_channel_download_finished(dl):
            channel_dirname = os.path.join(self.session.lm.mds.channels_dir, dl.get_def().get_name())
            self.session.lm.mds.process_channel_dir(channel_dirname, channel.public_key, external_thread=True)
            self.session.lm.mds._db.disconnect()

        def _on_failure(failure):
            self._logger.error("Error when processing channel dir download: %s", failure)

        def _on_success(_):
            with db_session:
                channel_upd = self.session.lm.mds.ChannelMetadata.get(public_key=channel.public_key, id_=channel.id_)
                channel_upd_dict = channel_upd.to_simple_dict()
            self.session.notifier.notify(NTFY_CHANNEL_ENTITY, NTFY_UPDATE,
                                         "%s:%s".format(hexlify(channel.public_key), str(channel.id_)),
                                         channel_upd_dict)

        finished_deferred = download.finished_deferred.addCallback(
            lambda dl: deferToThread(on_channel_download_finished, dl))
        finished_deferred.addCallbacks(_on_success, _on_failure)

        return download, finished_deferred

    def updated_my_channel(self, tdef):
        """
        Notify the core that we updated our channel.
        """
        with db_session:
            my_channel = self.session.lm.mds.ChannelMetadata.get_my_channel()
        if my_channel and my_channel.status == COMMITTED and not self.session.has_download(str(my_channel.infohash)):
            dcfg = DownloadStartupConfig(state_dir=self.session.config.get_state_dir())
            dcfg.set_dest_dir(self.session.lm.mds.channels_dir)
            dcfg.set_channel_download(True)
            self.session.lm.add(tdef, dcfg)
