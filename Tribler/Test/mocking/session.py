from twisted.internet.defer import Deferred

from .channel import MockChannel


class MockSession(object):

    class MockLm(object):

        class MockMds(object):

            class MockChannelMetadata(object):

                def __init__(self):
                    self.random_channels = []
                    self.channel_with_infohash = {}
                    self.channel_with_id = {}

                def set_random_channels(self, channel_list):
                    self.random_channels = channel_list

                def get_random_subscribed_channels(self, _):
                    return self.random_channels

                def add(self, channel):
                    self.channel_with_infohash[channel.infohash] = channel
                    self.channel_with_id[channel.public_key] = channel

                def get_channel_with_infohash(self, infohash):
                    return self.channel_with_infohash.get(infohash, None)

                def get_channel_with_id(self, public_key):
                    return self.channel_with_id.get(public_key, None)

                def from_dict(self, dictionary):
                    return MockChannel(**dictionary)

            ChannelMetadata = MockChannelMetadata()

        mds = MockMds()

        def __init__(self):
            self.downloaded_channel = None
            self.downloaded_channel_deferred = Deferred()
            self.downloading = False

        def set_download_channel(self, download):
            self.downloaded_channel = download

        def finish_download_channel(self):
            self.downloading = False
            self.downloaded_channel_deferred.callback(self.downloaded_channel)

        def download_channel(self, channel):
            self.downloading = True
            return self.downloaded_channel, self.downloaded_channel_deferred

    lm = MockLm()

    def __init__(self):
        self.known_infohashes = []

    def add_known_infohash(self, infohash):
        self.known_infohashes.append(infohash)

    def has_download(self, infohash):
        return infohash in self.known_infohashes
