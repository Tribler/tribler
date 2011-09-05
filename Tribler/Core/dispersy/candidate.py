from datetime import datetime

from dispersydatabase import DispersyDatabase
from member import Member

class Candidate(object):
    """
    A wrapper around the candidate table in the dispersy database.
    """

    def __init__(self, host, port, incoming_age, outgoing_age, external_age):
        assert isinstance(host, str)
        assert isinstance(port, int)
        assert isinstance(incoming_age, int)
        assert isinstance(outgoing_age, int)
        assert isinstance(external_age, int)
        self._address = (host, port)
        self._incoming_age = incoming_age
        self._outgoing_age = outgoing_age
        self._external_age = external_age

    @property
    def address(self):
        return self._address

    @property
    def host(self):
        return self._address[0]

    @property
    def port(self):
        return self._address[1]

    @property
    def incoming_age(self):
        return self._incoming_age

    @property
    def outgoing_age(self):
        return self._outgoing_age

    @property
    def external_age(self):
        return self._external_age

    @property
    def members(self):
        # TODO we should not just trust this information, a member can put any address in their
        # dispersy-identity message.  The database should contain a column with a 'verified' flag.
        # This flag is only set when a handshake was successfull.
        return [Member.get_instance(str(public_key))
                for public_key,
                in list(DispersyDatabase.get_instance().execute(u"SELECT public_key FROM user WHERE host = ? AND port = ? -- AND verified = 1", (unicode(self._address[0]), self._address[1])))]
