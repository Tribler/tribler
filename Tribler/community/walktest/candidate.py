from time import time

class Candidate(object):
    def __init__(self, internal_address, external_address, introduction_requests=0, introduction_responses=0, puncture_requests=0, punctures=0):
        assert isinstance(internal_address, tuple)
        assert len(internal_address) == 2
        assert isinstance(internal_address[0], str)
        assert isinstance(internal_address[1], int)
        assert isinstance(external_address, tuple)
        assert len(external_address) == 2
        assert isinstance(external_address[0], str)
        assert isinstance(external_address[1], int)
        self._internal_address = internal_address
        self._external_address = external_address
        self._stamp = time()
        self._introduction_requests = introduction_requests
        self._introduction_responses = introduction_responses
        self._puncture_requests = puncture_requests
        self._punctures = punctures

    @property
    def internal_address(self):
        return self._internal_address

    @property
    def external_address(self):
        return self._external_address
    
    @property
    def stamp(self):
        return self._stamp

    @property
    def is_walk(self):
        return bool(self._introduction_responses)

    @property
    def is_stumble(self):
        return bool(self._introduction_requests)

    def inc_introduction_requests(self, internal_address, external_address):
        assert isinstance(internal_address, tuple)
        assert len(internal_address) == 2
        assert isinstance(internal_address[0], str)
        assert isinstance(internal_address[1], int)
        assert isinstance(external_address, tuple)
        assert len(external_address) == 2
        assert isinstance(external_address[0], str)
        assert isinstance(external_address[1], int)
        self._internal_address = internal_address
        self._external_address = external_address
        self._stamp = time()
        self._introduction_requests += 1

    def inc_introduction_responses(self):
        self._stamp = time()
        self._introduction_responses += 1

    def inc_puncture_requests(self):
        self._stamp = time()
        self._puncture_requests += 1

    def inc_punctures(self):
        self._stamp = time()
        self._punctures += 1
