from Tribler.dispersy.payload import Payload


class StatisticsRequestPayload(Payload):
    '''
    Request statistics for key 'key' from peer.
    '''

    class Implementation(Payload.Implementation):

        def __init__(self, meta, stats_type):
            super(StatisticsRequestPayload.Implementation, self).__init__(meta)
            self.stats_type = stats_type


class StatisticsResponsePayload(Payload):

    class Implementation(Payload.Implementation):

        def __init__(self, meta, stats_type, records):
            super(StatisticsResponsePayload.Implementation, self).__init__(meta)
            self.stats_type = stats_type
            self.records = records
