class MockDownload(object):

    class MockTdef(object):

        def __init__(self):
            self.infohash = ""

        def set_infohash(self, infohash):
            self.infohash = infohash

        def get_infohash(self):
            return self.infohash

    tdef = MockTdef()

    def get_num_connected_seeds_peers(self):
        return 42, 1337
