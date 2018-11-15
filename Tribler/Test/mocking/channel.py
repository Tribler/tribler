class MockChannel(object):

    def __init__(self, infohash, public_key, title, version, votes=0, local_version=0):
        self.infohash = infohash
        self.public_key = public_key
        self.title = title
        self.version = version
        self.votes = votes
        self.local_version = local_version
