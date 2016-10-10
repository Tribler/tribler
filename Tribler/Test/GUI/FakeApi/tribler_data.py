from random import randint, sample
from models.channel import Channel
from models.download import Download
from models.torrent import Torrent


CREATE_MY_CHANNEL = True


class TriblerData:

    def __init__(self):
        self.channels = []
        self.torrents = []
        self.torrent_files = {}
        self.subscribed_channels = set()
        self.downloads = []
        self.my_channel = -1
        self.rss_feeds = []

    def generate(self):
        self.read_torrent_files()
        self.generate_torrents()
        self.generate_channels()
        self.assign_subscribed_channels()
        self.generate_downloads()
        self.generate_rss_feeds()

    # Generate channels from the random_channels file
    def generate_channels(self):
        num_channels = randint(100, 200)
        for i in range(0, num_channels):
            self.channels.append(Channel(i, name="Channel %d" % i, description="Description of channel %d" % i))

        if CREATE_MY_CHANNEL:
            # Pick one of these channels as your channel
            self.my_channel = randint(0, len(self.channels))

    def assign_subscribed_channels(self):
        # Make between 10 and 50 channels subscribed channels
        num_subscribed = randint(10, 50)
        for i in range(0, num_subscribed):
            channel_index = randint(0, len(self.channels) - 1)
            self.subscribed_channels.add(channel_index)
            self.channels[channel_index].subscribed = True

    def read_torrent_files(self):
        with open("data/torrent_files.dat") as torrent_files_file:
            content = torrent_files_file.readlines()
            for torrent_file_line in content:
                parts = torrent_file_line.split("\t")
                torrent_id = parts[0]
                if torrent_id not in self.torrent_files:
                    self.torrent_files[torrent_id] = []
                self.torrent_files[torrent_id].append({"path": parts[1], "length": parts[2]})

    def generate_torrents(self):
        # Create random torrents in channels
        with open("data/random_torrents.dat") as random_torrents:
            content = random_torrents.readlines()
            for random_torrent in content:
                random_torrent = random_torrent.rstrip()
                torrent_parts = random_torrent.split("\t")
                torrent = Torrent(*torrent_parts)
                if torrent_parts[0] in self.torrent_files:
                    torrent.files = self.torrent_files[torrent_parts[0]]
                self.torrents.append(torrent)

    def generate_rss_feeds(self):
        for i in range(randint(10, 30)):
            self.rss_feeds.append('http://test%d.com/feed.xml' % i)

    def get_channel_with_id(self, id):
        for channel in self.channels:
            if str(channel.id) == id:
                return channel

    def get_channel_with_cid(self, cid):
        for channel in self.channels:
            if str(channel.cid) == cid:
                return channel

    def get_my_channel(self):
        if self.my_channel == -1:
            return None
        return self.channels[self.my_channel]

    def get_download_with_infohash(self, infohash):
        for download in self.downloads:
            if download.torrent.infohash == infohash:
                return download

    def start_random_download(self):
        random_torrent = sample(self.torrents, 1)[0]
        self.downloads.append(Download(random_torrent))

    def generate_downloads(self):
        for _ in xrange(randint(10, 30)):
            self.start_random_download()
