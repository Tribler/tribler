from .community import BarterCommunity


class BarterCrawler(object):

    def __init__(self, dispersy):
        masters = BarterCommunity.get_master_members(dispersy)
        assert len(masters) == 1
        self._community = BarterCommunity.load_community(dispersy, masters[0])

    def next_testcase(self):
        # TODO we will remove next_testcase once we cleanup the script starting
        pass
