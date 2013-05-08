from .community import BarterCommunity

class DummySwiftProcess(object):
    def set_subscribe_channel_close(self, *args, **kargs):
        pass

class BarterCrawler(object):
    def __init__(self, dispersy):
        masters = BarterCommunity.get_master_members(dispersy)
        assert len(masters) == 1
        self._community = BarterCommunity.load_community(dispersy, masters[0], DummySwiftProcess())

    def next_testcase(self):
        # TODO we will remove next_testcase once we cleanup the script starting
        pass
