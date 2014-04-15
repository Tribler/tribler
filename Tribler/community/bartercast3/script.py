from .community import BarterCommunity


class DummySwiftProcess(object):

    def set_subscribe_channel_close(self, *args, **kargs):
        pass


class BarterCrawler(object):

    def __init__(self, dispersy, my_member):
        masters = BarterCommunity.get_master_members(dispersy)
        assert len(masters) == 1
        self._community = BarterCommunity(dispersy, masters[0], my_member, DummySwiftProcess())

    def next_testcase(self):
        # TODO we will remove next_testcase once we cleanup the script starting
        pass
