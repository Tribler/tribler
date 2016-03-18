from Tribler.dispersy.payload import Payload


class CrawlRequestPayload(Payload):
    """
    Request a crawl of blocks starting with a specific sequence number or the first if -1.
    """

    class Implementation(Payload.Implementation):
        def __init__(self, meta, requested_sequence_number=-1):
            super(CrawlRequestPayload.Implementation, self).__init__(meta)
            self._requested_sequence_number = requested_sequence_number

        @property
        def requested_sequence_number(self):
            return self._requested_sequence_number


class CrawlResumePayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta):
            super(CrawlResumePayload.Implementation, self).__init__(meta)


class HalfBlockPayload(Payload):
    """
    Payload for message that ships a half block
    """

    class Implementation(Payload.Implementation):
        def __init__(self, meta, block):
            super(HalfBlockPayload.Implementation, self).__init__(meta)
            # self._block = block
            self.block = block

        # @property
        # def block(self):
        #     return self._block


class FullBlockPayload(Payload):
    """
    Payload for message that ships two _linked_ half blocks
    """

    class Implementation(Payload.Implementation):
        def __init__(self, meta, block_this, block_that):
            super(FullBlockPayload.Implementation, self).__init__(meta)
            self.block_this = block_this
            self.block_that = block_that
            # TODO: check that the blocks are indeed linked
