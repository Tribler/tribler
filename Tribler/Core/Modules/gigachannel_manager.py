from __future__ import absolute_import

import os
from binascii import hexlify

from ipv8.taskmanager import TaskManager

from pony.orm import db_session

from twisted.internet.defer import inlineCallbacks
from twisted.internet.task import LoopingCall
from twisted.internet.threads import deferToThread

from Tribler.Core.DownloadConfig import DownloadStartupConfig
from Tribler.Core.Modules.MetadataStore.OrmBindings.channel_node import COMMITTED
from Tribler.Core.TorrentDef import TorrentDef, TorrentDefNoMetainfo
from Tribler.Core.simpledefs import DLSTATUS_SEEDING, NTFY_CHANNEL_ENTITY, NTFY_UPDATE


PROCESS_CHANNEL_DIR = 1
REMOVE_CHANNEL_DOWNLOAD = 2


class GigaChannelManager(TaskManager):
    """
    This class represents the main manager for gigachannels.
    It provides methods to manage channels, download new channels or remove existing ones.
    """

    def __init__(self, session):
        super(GigaChannelManager, self).__init__()
        self.session = session
        self.channels_lc = None

        # We queue up processing of the channels because we do it in a separate thread, and we don't want
        # to run more that one of these simultaneously
        self.channels_processing_queue = {}
        self.processing = False

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
                    mdblob_path = os.path.join(self.session.lm.mds.channels_dir, my_channel.dir_name + ".mdblob")
                    tdef = None
                    if os.path.exists(torrent_path) and os.path.exists(mdblob_path):
                        try:
                            tdef = TorrentDef.load(torrent_path)
                        except IOError:
                            self._logger.warning("Can't open personal channel torrent file. Will try to regenerate it.")
                    tdef = tdef if (tdef and tdef.infohash == str(my_channel.infohash)) else\
                        TorrentDef.load_from_dict(my_channel.consolidate_channel_torrent())
                    self.updated_my_channel(tdef)
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
            # FIXME: if someone is subscribed to more than 1000 channels, they are in trouble...
            channels = self.session.lm.mds.ChannelMetadata.get_entries(last=1000, subscribed=True)
            subscribed_infohashes = [bytes(c.infohash) for c in list(channels)]
            dirnames = [c.dir_name for c in channels]

        # TODO: add some more advanced logic for removal of older channel versions
        cruft_list = [(d, d.get_def().get_name_utf8() not in dirnames)
                      for d in self.session.lm.get_channel_downloads()
                      if bytes(d.get_def().infohash) not in subscribed_infohashes]

        for d, remove_content in cruft_list:
            self.channels_processing_queue[d.get_def().infohash] = (REMOVE_CHANNEL_DOWNLOAD, (d, remove_content))

    def service_channels(self):
        if self.processing:
            return
        try:
            self.remove_cruft_channels()
        except Exception:
            self._logger.exception("Error when tried to check for cruft channels")
        try:
            self.check_channels_updates()
        except Exception:
            self._logger.exception("Error when checking for channel updates")

        if not self.processing:
            return self.process_queued_channels()

    @inlineCallbacks
    def process_queued_channels(self):
        while self.channels_processing_queue:
            infohash, (action, data) = next(iter(self.channels_processing_queue.items()))
            self.channels_processing_queue.pop(infohash)
            self.processing = True
            if action == PROCESS_CHANNEL_DIR:
                yield self.process_channel_dir_threaded(data)  # data is a channel
            elif action == REMOVE_CHANNEL_DOWNLOAD:
                yield self.remove_channel_download(data)  # data is a tuple (download, remove_content bool)

    def check_channels_updates(self):
        """
        Check whether there are channels that are updated. If so, download the new version of the channel.
        """
        # FIXME: These naughty try-except-pass workarounds are necessary to keep the loop going in all circumstances

        with db_session:
            channels = list(self.session.lm.mds.ChannelMetadata.get_updated_channels())

        for channel in channels:
            try:
                if not self.session.has_download(str(channel.infohash)):
                    self._logger.info("Downloading new channel version %s ver %i->%i",
                                      hexlify(str(channel.public_key)),
                                      channel.local_version, channel.timestamp)
                    self.download_channel(channel)
                elif self.session.get_download(str(channel.infohash)).get_state().get_status() == DLSTATUS_SEEDING:
                    self._logger.info("Processing previously downloaded, but unprocessed channel torrent %s ver %i->%i",
                                      hexlify(str(channel.public_key)),
                                      channel.local_version, channel.timestamp)
                    self.channels_processing_queue[channel.infohash] = (PROCESS_CHANNEL_DIR, channel)
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

    def remove_channel_download(self, to_remove):
        """
        :param to_remove: a tuple (download_to_remove=download, remove_files=Bool)
        """

        # TODO: make file removal from older versions safe (i.e. check if it overlaps with newer downloads)

        """
        files_to_remove = []
        for download in to_remove_list:
            files_to_remove.extend(self.safe_files_to_remove(download))
        """

        def _on_failure(failure):
            self._logger.error("Error when removing the channel download: %s", failure)
            self.processing = False

        def _on_success(_):
            self.processing = False

        d, remove_content = to_remove
        deferred = self.session.remove_download(d, remove_content=remove_content)
        deferred.addCallbacks(_on_success, _on_failure)
        self.register_task(u'remove_channel' + d.tdef.get_name_utf8() + u'-' + hexlify(d.tdef.get_infohash()),
                           deferred)

        """
        def _on_torrents_removed(torrent):
            print files_to_remove
        dl = DeferredList(removed_list)
        dl.addCallback(_on_torrents_removed)
        self.register_task(u'remove_channels_files-' + "_".join([d.tdef.get_name_utf8() for d in to_remove_list]), dl)
        """

        return deferred

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

        def _add_channel_to_processing_queue(_):
            self.channels_processing_queue[channel.infohash] = (PROCESS_CHANNEL_DIR, channel)

        finished_deferred = download.finished_deferred.addCallback(_add_channel_to_processing_queue)

        return download, finished_deferred

    def process_channel_dir_threaded(self, channel):

        def _process_download():
            channel_dirname = os.path.join(self.session.lm.mds.channels_dir, channel.dir_name)
            self.session.lm.mds.process_channel_dir(channel_dirname, channel.public_key, channel.id_,
                                                    external_thread=True)
            self.session.lm.mds._db.disconnect()

        def _on_failure(failure):
            self._logger.error("Error when processing channel dir download: %s", failure)
            self.processing = False

        def _on_success(_):
            with db_session:
                channel_upd = self.session.lm.mds.ChannelMetadata.get(public_key=channel.public_key, id_=channel.id_)
                channel_upd_dict = channel_upd.to_simple_dict()
            self.session.notifier.notify(NTFY_CHANNEL_ENTITY, NTFY_UPDATE,
                                         "%s:%s".format(hexlify(channel.public_key), str(channel.id_)),
                                         channel_upd_dict)
            self.processing = False

        return deferToThread(_process_download).addCallbacks(_on_success, _on_failure)

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
