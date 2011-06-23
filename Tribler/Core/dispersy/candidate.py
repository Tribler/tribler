from datetime import datetime

from dispersydatabase import DispersyDatabase
from member import Member

class Candidate(object):
    """
    A wrapper around the candidate table in the dispersy database.
    """
    _datetime_format = "%Y-%m-%d %H:%M:%S"

    def __init__(self, host, port, incoming_time, outgoing_time, external_time):
        assert isinstance(host, str)
        assert isinstance(port, int)
        assert isinstance(incoming_time, unicode)
        assert isinstance(outgoing_time, unicode)
        assert isinstance(external_time, unicode)
        self._host = host
        self._port = port
        self._incoming_time = incoming_time
        self._outgoing_time = outgoing_time
        self._external_time = external_time

    @property
    def address(self):
        return (self._host, self._port)

    @property
    def host(self):
        return self._host

    @property
    def port(self):
        return self._port

    @property
    def incoming_time(self):
        return datetime.strptime(self._incoming_time, self._datetime_format)

    @property
    def outgoing_time(self):
        return datetime.strptime(self._outgoing_time, self._datetime_format)

    @property
    def external_time(self):
        return datetime.strptime(self._external_time, self._datetime_format)

    @property
    def members(self):
        # TODO we should not just trust this information, a member can put any address in their
        # dispersy-identity message.  The database should contain a column with a 'verified' flag.
        # This flag is only set when a handshake was successfull.
        return [Member.get_instance(str(public_key))
                for public_key,
                in list(DispersyDatabase.get_instance().execute(u"SELECT public_key FROM user WHERE host = ? AND port = ? -- AND verified = 1", (unicode(self._host), self._port)))]
