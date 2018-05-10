import os

from Tribler.community.allchannel2.payload import ChannelPayload
from Tribler.community.allchannel2.structures import Channel
from Tribler.Core.DownloadConfig import DefaultDownloadStartupConfig
from Tribler.pyipv8.ipv8.deprecated.community import Community
from Tribler.pyipv8.ipv8.deprecated.payload_headers import BinMemberAuthenticationPayload, GlobalTimeDistributionPayload
from Tribler.pyipv8.ipv8.peer import Peer


def infohash_to_magnet(infohash):
    """
    Tranform an info hash to a magnet link.

    :param infohash: the infohash to convert
    :return: the magnet link belonging to this info hash
    """
    return "magnet:?xt=urn:btih:" + infohash


class AllChannel2Community(Community):
    """
    AllChannel 2.0

    My channel administration usage:
     1. __init__()
     2. load_channels(): performs heavy disk I/O
     3. add_magnetlink()/remove_magnetlink(): change the contents of my channel
     4. fetch and seed my_channel_torrent (automatically committed)
    """
    master_peer = Peer(("307e301006072a8648ce3d020106052b81040024036a000400d2aaf87af3a1743286" +
                        "fe9a9b13abffe35fe1fc7fd5e40e5d587b01cbefa4eece1c9c8fca4767684acbe8b2d" +
                        "050c09eb7f2a9d000083c293d9ed9cc562edfa330d178e0516b068de4509193cd38b3" +
                        "bb22476177ede8f944010e9fb8843e15ef4fe829bc569de649").decode('hex'))

    def __init__(self, my_peer, endpoint, network, working_directory="./channels", tribler_session=None):
        """
        Initialize the AllChannel2 Community.

        :param my_peer: the Peer representing my peer
        :param endpoint: the Endpoint object to use
        :param network: the Network object to use
        :param working_directory: the folder where all of the channels are stored
        """
        super(AllChannel2Community, self).__init__(my_peer, endpoint, network)
        self.working_directory = working_directory
        self.channels = {}
        self.my_channel_name = self.my_peer.mid.encode("hex")
        self.tribler_session = tribler_session

        # Internals, do not touch!
        self._my_channel_info_hash = None
        self._my_channel_torrent = None
        self.decode_map.update({chr(1): self.on_channel})

    def load_channels(self):
        """
        Load all known Channels from the working directory.

        :returns: None
        """
        channel_directories = [folder for folder in os.listdir(self.working_directory)
                               if os.path.isdir(os.path.join(self.working_directory, folder))]
        for folder in channel_directories:
            self.load_channel(folder)
        if not self.my_channel_name in self.channels:
            os.makedirs(os.path.abspath(os.path.join(self.working_directory, self.my_channel_name)))

    def load_channel(self, channel):
        """
        Load a single channel from the folder structure.

        :param channel: the channel name
        :returns: None
        """
        real_path = os.path.abspath(os.path.join(self.working_directory, channel))
        if os.path.isdir(real_path):
            channel_instance = Channel(channel, self.working_directory, allow_edit=(channel == self.my_channel_name))
            channel_instance.load()
            self.channels[channel] = channel_instance

    def _commit_my_channel(self):
        """
        Commit the channel based on my_peer.

        :returns: None
        """
        my_channel = self.channels.get(self.my_channel_name,
                                       Channel(self.my_channel_name, self.working_directory, True))
        my_channel.commit()
        try:
            self._my_channel_torrent, self._my_channel_info_hash = my_channel.make_torrent()
        except RuntimeError:
            self.logger.warning("Tried to make torrent, but the Channel was empty!")
        self.channels[self.my_channel_name] = my_channel

    def _dirty_cache(self):
        """
        Turn my channel dirty.
        This invalidates the info hash and torrent file, which will have to be recreated.

        :returns: None
        """
        self._my_channel_info_hash = None
        self._my_channel_torrent = None

    @property
    def my_channel_info_hash(self):
        """
        The info hash representing my channel.

        :return: (20 byte str) info hash of my channel
        """
        if not self._my_channel_info_hash:
            self._commit_my_channel()
        return self._my_channel_info_hash

    @property
    def my_channel_magnet_link(self):
        """
        The magnet link representing my channel.

        :return: the (stripped) magnet link of my channel
        """
        if not self._my_channel_info_hash:
            self._commit_my_channel()
        return infohash_to_magnet(self._my_channel_info_hash)

    @property
    def my_channel_torrent(self):
        """
        The torrent file representing my channel.

        :return: the filename of the torrent for my channel
        """
        if not self._my_channel_torrent:
            self._commit_my_channel()
        return self._my_channel_torrent

    def add_magnetlink(self, magnetlink):
        """
        Add a magnet link to my channel.

        :param magnetlink: the (20 byte str) magnet link to add
        :returns: None
        """
        if not self.my_channel_name in self.channels:
            self._commit_my_channel()
        self.channels[self.my_channel_name].add_magnetlink(magnetlink)
        self._dirty_cache()

    def remove_magnetlink(self, magnetlink):
        """
        Remove a magnet link from my channel.

        :param magnetlink: the (20 byte str) magnet link to add
        :returns: None
        """
        if not self.my_channel_name in self.channels:
            self._commit_my_channel()
        self.channels[self.my_channel_name].remove_magnetlink(magnetlink)
        self._dirty_cache()

    def get_channels(self):
        """
        Get all known channels.

        :return: the names of the channels we know about (including our own)
        """
        return self.channels.keys()

    def get_magnetlinks(self, channel):
        """
        Get all the magnet links from a specific channel name.

        :param channel: the channel name
        :return: the magnet links belonging to that channel
        """
        channel_instance = self.channels.get(channel, None)
        return channel_instance.get_magnetlinks() if channel_instance else []

    def create_channel_message(self):
        """
        Create a channel message for my channel.

        :return: the channel message
        """
        global_time = self.claim_global_time()
        payload = ChannelPayload(self.my_channel_info_hash).to_pack_list()
        auth = BinMemberAuthenticationPayload(self.my_peer.public_key.key_to_bin()).to_pack_list()
        dist = GlobalTimeDistributionPayload(global_time).to_pack_list()

        return self._ez_pack(self._prefix, 1, [auth, dist, payload])

    def download_finished(self, download):
        """
        Callback for when a Channel download finished.
        Load in the Channel data.

        :param download: the LibtorrentDownloadImpl instance
        :returns: None
        """
        real_path = download.dlconfig.get_dest_dir()
        rel_path = os.path.relpath(self.working_directory, real_path)
        self.load_channel(rel_path)

    def on_channel(self, source_address, data):
        """
        Callback for when a ChannelPayload message is received.
        """
        auth, _, payload = self._ez_unpack_auth(ChannelPayload, data)
        channel = Peer(auth.public_key_bin).mid.encode('hex')
        # If we don't know about this channel, respond with our own
        if channel not in self.channels:
            if self.my_channel_info_hash and source_address not in self.network.blacklist:
                packet = self.create_channel_message()
                self.endpoint.send(source_address, packet)
            # And start downloading it, if we are hooked up to a Tribler session
            if self.tribler_session:
                download_config = DefaultDownloadStartupConfig.getInstance()
                dest_dir = os.path.abspath(os.path.join(self.working_directory, channel))
                download_config.set_dest_dir(dest_dir)
                add_deferred = self.tribler_session.start_download_from_uri(infohash_to_magnet(payload.info_hash),
                                                                            download_config)
                add_deferred.addCallback(lambda download:
                                         download.deferred_finished).addCallback(self.download_finished)

    def on_introduction_response(self, source_address, data):
        """
        Callback for when an introduction response is received.

        We extend the functionality by sharing our channel with the other side.
        """
        super(AllChannel2Community, self).on_introduction_response(source_address, data)

        if self.my_channel_info_hash and source_address not in self.network.blacklist:
            packet = self.create_channel_message()
            self.endpoint.send(source_address, packet)
