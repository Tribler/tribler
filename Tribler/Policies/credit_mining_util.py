"""
File containing function used in credit mining module.
"""


import os
from binascii import hexlify, unhexlify

from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.simpledefs import NTFY_CHANNELCAST
from Tribler.Core.simpledefs import NTFY_TORRENTS
from Tribler.Core.simpledefs import NTFY_VOTECAST
from Tribler.Main.Utility.GuiDBTuples import CollectedTorrent, RemoteTorrent, NotCollectedTorrent, Channel, \
    ChannelTorrent
from Tribler.Policies.defs import SIMILARITY_TRESHOLD
from Tribler.dispersy.taskmanager import TaskManager


def validate_source_string(source):
    """
    Function to check whether a source string is a valid source or not
    """
    return unhexlify(source) if len(source) == 40 and not source.startswith("http") else source


def levenshtein_dist(t1_fname, t2_fname):
    """
    Calculates the Levenshtein distance between a and b.

    Levenshtein distance (LD) is a measure of the similarity between two strings.
    (from http://people.cs.pitt.edu/~kirk/cs1501/Pruhs/Fall2006/Assignments/editdistance/Levenshtein%20Distance.htm)
    """
    len_t1_fname, len_t2_fname = len(t1_fname), len(t2_fname)
    if len_t1_fname > len_t2_fname:
        # Make sure len_t1_fname <= len_t2_fname, to use O(min(len_t1_fname,len_t2_fname)) space
        t1_fname, t2_fname = t2_fname, t1_fname
        len_t1_fname, len_t2_fname = len_t2_fname, len_t1_fname

    current = range(len_t1_fname + 1)
    for i in xrange(1, len_t2_fname + 1):
        previous, current = current, [i] + [0] * len_t1_fname
        for j in xrange(1, len_t1_fname + 1):
            add, delete = previous[j] + 1, current[j - 1] + 1
            change = previous[j - 1]
            if t1_fname[j - 1] != t2_fname[i - 1]:
                change += 1
            current[j] = min(add, delete, change)

    return current[len_t1_fname]


def source_to_string(source_obj):
    return hexlify(source_obj) if len(source_obj) == 20 and not (source_obj.startswith('http://')
                                                                 or source_obj.startswith('https://')) else source_obj


def string_to_source(source_str):
    # don't need to handle null byte because lazy evaluation
    return source_str.decode('hex') \
        if len(source_str) == 40 and not (os.path.isdir(source_str) or source_str.startswith('http://')) else source_str


def compare_torrents(torrent_1, torrent_2):
    """
    comparing swarms. We don't want to download the same swarm with different infohash
    :return: whether those t1 and t2 similar enough
    """
    files1 = [files for files in torrent_1['metainfo'].get_files_with_length() if files[1] > 1024 * 1024]
    files2 = [files for files in torrent_2['metainfo'].get_files_with_length() if files[1] > 1024 * 1024]

    if len(files1) == len(files2):
        for ft1 in files1:
            for ft2 in files2:
                if ft1[1] != ft2[1] or levenshtein_dist(ft1[0], ft2[0]) > SIMILARITY_TRESHOLD:
                    return False
        return True
    return False


def ent2chr(input_str):
    """
    Function to unescape literal string in XML to symbols
    source : http://www.gossamer-threads.com/lists/python/python/177423
    """
    code = input_str.group(1)
    code_int = int(code) if code.isdigit() else int(code[1:], 16)
    return chr(code_int) if code_int < 256 else '?'

# TODO(ardhi) : temporary function until GUI and core code are separated
class TorrentManagerCM(TaskManager):
    """
    *Temporary* class to handle load torrent.

    Adapted from TorrentManager in SearchGridManager
    """
    def __init__(self, session):
        super(TorrentManagerCM, self).__init__()

        self.session = session
        self.torrent_db = self.session.open_dbhandler(NTFY_TORRENTS)
        self.channelcast_db = self.session.open_dbhandler(NTFY_CHANNELCAST)
        self.votecastdb = self.session.open_dbhandler(NTFY_VOTECAST)

        self.dslist = []

    def load_torrent(self, torrent, callback=None):
        """
        function to load torrent dictionary to torrent object.

        From TorrentManager.loadTorrent in SearchGridManager
        """

        # session is quitting
        if not (self.session and self.session.get_torrent_store() and self.session.lm.torrent_store):
            return

        if not isinstance(torrent, CollectedTorrent):
            if torrent.torrent_id <= 0:
                torrent_id = self.torrent_db.getTorrentID(torrent.infohash)
                if torrent_id:
                    torrent.update_torrent_id(torrent_id)

            if not self.session.has_collected_torrent(torrent.infohash):
                files = []
                trackers = []

                # see if we have most info in our tables
                if isinstance(torrent, RemoteTorrent):
                    torrent_id = self.torrent_db.getTorrentID(torrent.infohash)
                else:
                    torrent_id = torrent.torrent_id

                trackers.extend(self.torrent_db.getTrackerListByTorrentID(torrent_id))

                if 'DHT' in trackers:
                    trackers.remove('DHT')
                if 'no-DHT' in trackers:
                    trackers.remove('no-DHT')

                # replacement # self.downloadTorrentfileFromPeers(torrent, None)
                if self.session.has_download(torrent.infohash):
                    return False

                if torrent.query_candidates is None or len(torrent.query_candidates) == 0:
                    self.session.download_torrentfile(torrent.infohash, None, 0)
                else:
                    for candidate in torrent.query_candidates:
                        self.session.download_torrentfile_from_peer(candidate, torrent.infohash, None, 0)

                torrent = NotCollectedTorrent(torrent, files, trackers)

            else:
                tdef = TorrentDef.load_from_memory(self.session.get_collected_torrent(torrent.infohash))

                if torrent.torrent_id <= 0:
                    del torrent.torrent_id

                torrent = CollectedTorrent(torrent, tdef)

        # replacement # self.library_manager.addDownloadState(torrent)
        for dl_state in self.dslist:
            torrent.addDs(dl_state)

        # return
        if callback is not None:
            callback(torrent)
        else:
            return torrent

    def create_torrents(self, tor_values, _, channel_dict):
        """
        function to create torrents from channel. Adapted from
        ChannelManager in SearchGridManager
        """

        #adding new channel from the one that can't be detected from torrent values
        fetch_channels = set(hit[0] for hit in tor_values if hit[0] not in channel_dict)
        if len(fetch_channels) > 0:
            channels_new_dict = self.channelcast_db.getChannels(fetch_channels)
            channels = []
            for hit in channels_new_dict:
                channel = Channel(*hit)
                channels.append(channel)

            for channel in channels:
                channel_dict[channel.id] = channel

        # creating torrents
        torrents = []
        for hit in tor_values:
            if hit:
                chan_torrent = ChannelTorrent(*hit[1:] + [channel_dict.get(hit[0], None), None])
                chan_torrent.torrent_db = self.torrent_db
                chan_torrent.channelcast_db = self.channelcast_db

                if chan_torrent.name:
                    torrents.append(chan_torrent)

        return torrents
