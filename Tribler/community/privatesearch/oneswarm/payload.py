class SearchCancelPayload(Payload):
    class Implementation(Payload.Implementation):
        def __init__(self, meta, identifier):
            if __debug__:
                assert isinstance(identifier, int), type(identifier)

            super(SearchCancelPayload.Implementation, self).__init__(meta)
            self._identifier = identifier

        @property
        def identifier(self):
            return self._identifier
