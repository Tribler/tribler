# Python 2.5 features
from __future__ import with_statement

"""
For each peer that we have the public key, we have one Member instance.  Each member instance is
used to uniquely identify a peer.  Special Member subclasses exist to identify, for instance,
youself.
"""

from hashlib import sha1

from singleton import Parameterized1Singleton
from dispersydatabase import DispersyDatabase
from crypto import ec_from_private_bin, ec_from_public_bin, ec_to_public_bin, ec_signature_length, ec_verify, ec_sign
from encoding import encode, decode

if __debug__:
    from dprint import dprint

class Public(object):
    @property
    def mid(self):
        """
        The member id.  This is the 20 byte sha1 hash over the public key.
        """
        raise NotImplementedError()

    @property
    def public_key(self):
        """
        The public key.  This is binary representation of the public key.
        """
        raise NotImplementedError()

    @property
    def signature_length(self):
        """
        The length, in bytes, of a signature.
        """
        raise NotImplementedError()

    def verify(self, data, signature, offset=0, length=0):
        """
        Verify that DATA, starting at OFFSET up to LENGTH bytes, was
        signed by this member and matches SIGNATURE.

        DATA is the signed data and the signature concatenated.
        OFFSET is the offset for the signed data.
        LENGTH is the length of the signature and the data, in bytes.

        Returns True or False.
        """
        raise NotImplementedError()

class Private(object):
    @property
    def private_key(self):
        raise NotImplementedError()

    def sign(self, data, offset=0, length=0):
        """
        Sign DATA using our private key.  Returns a signature.
        """
        raise NotImplementedError()

class Member(Public, Parameterized1Singleton):
    """
    The Member class represents a single member in the Dispersy database.

    There should only be one or less Member instance for each member in the database.  To ensure
    this, each Member instance must be created or retrieved using has_instance or get_instance.
    """

    # This _singleton_instances is very important.  It ensures that all subclasses of Member use the
    # same dictionary when looking for a public_key.  Otherwise each subclass would get its own
    # _singleton_instances dictionary.
    _singleton_instances = {}

    def __init__(self, public_key, ec=None, sync_with_database=True):
        """
        Create a new Member instance.  Member instances must be reated or retrieved using
        has_instance or get_instance.

        PUBLIC_KEY must be a string giving the public EC key in DER format.  EC is an optional EC
        object (given when created from private key).
        """
        assert isinstance(public_key, str)
        assert not public_key.startswith("-----BEGIN")
        assert isinstance(sync_with_database, bool)
        self._public_key = public_key
        if ec is None:
            self._ec = ec_from_public_bin(public_key)
        else:
            self._ec = ec

        self._signature_length = ec_signature_length(self._ec)
        self._mid = sha1(public_key).digest()

        self._database_id = -1
        self._address = ("", -1)
        self._tags = []

        # sync with database
        if sync_with_database:
            if not self.update():
                database = DispersyDatabase.get_instance()
                database.execute(u"INSERT INTO user(mid, public_key) VALUES(?, ?)", (buffer(self._mid), buffer(self._public_key)))
                self._database_id = database.last_insert_rowid

    def update(self):
        """
        Update this instance from the database
        """
        try:
            execute = DispersyDatabase.get_instance().execute

            self._database_id, host, port, tags = execute(u"SELECT id, host, port, tags FROM user WHERE public_key = ? LIMIT 1", (buffer(self._public_key),)).next()
            self._address = (str(host), port)
            self._tags = []
            if tags:
                self._tags = list(execute(u"SELECT key FROM tag WHERE value & ?", (tags,)))
            return True

        except StopIteration:
            return False

    @property
    def mid(self):
        return self._mid

    @property
    def public_key(self):
        return self._public_key

    @property
    def signature_length(self):
        return self._signature_length

    @property
    def database_id(self):
        """
        The database id.  This is the unsigned integer used to store
        this member in the Dispersy database.
        """
        assert self._database_id > 0, "No database id set.  Please call member.update()"
        return self._database_id

    @property
    def address(self):
        """
        The most recently advertised address for this member.

        Addresses are advertised using a dispersy-identity message,
        and the most recent -per member- is stored and forwarded.  The
        address will be ('', -1) until at least one dispersy-identity
        message for the member is received.
        """
        return self._address

    def _set_tag(self, tag, value):
        assert isinstance(tag, unicode)
        assert tag in [u"store", u"ignore", u"drop"]
        assert isinstance(value, bool)
        if __debug__: dprint(tag, " -> ", value)
        if value:
            if tag in self._tags:
                # the tag is already set
                return False
            self._tags.append(tag)

        else:
            if not tag in self._tags:
                # the tag isn't there to begin with
                return False
            self._tags.remove(tag)

        with DispersyDatabase.get_instance() as execute:
            # todo: at some point we may want to optimize this.  for now this is a feature that will
            # probably not be used often hence we leave it like this.
            tags = list(execute(u"SELECT key, value FROM tag"))
            int_tags = [0, 0] + [key for key, value in tags if value in self._tags]
            reduced = reduce(lambda a, b: a | b, int_tags)
            execute(u"UPDATE user SET tags = ? WHERE public_key = ?", (reduced, buffer(self._public_key),))
        return True

    # @property
    def __get_must_store(self):
        return u"store" in self._tags
    # @must_store.setter
    def __set_must_store(self, value):
        return self._set_tag(u"store", value)
    # .setter was introduced in Python 2.6
    must_store = property(__get_must_store, __set_must_store)

    # @property
    def __get_must_ignore(self):
        return u"ignore" in self._tags
    # @must_ignore.setter
    def __set_must_ignore(self, value):
        return self._set_tag(u"ignore", value)
    # .setter was introduced in Python 2.6
    must_ignore = property(__get_must_ignore, __set_must_ignore)

    # @property
    def __get_must_drop(self):
        return u"drop" in self._tags
    # @must_drop.setter
    def __set_must_drop(self, value):
        return self._set_tag(u"drop", value)
    # .setter was introduced in Python 2.6
    must_drop = property(__get_must_drop, __set_must_drop)

    def verify(self, data, signature, offset=0, length=0):
        assert isinstance(data, str)
        assert isinstance(signature, str)
        assert isinstance(offset, (int, long))
        assert isinstance(length, (int, long))
        length = length or len(data)
        return self._signature_length == len(signature) and ec_verify(self._ec, sha1(data[offset:offset+length]).digest(), signature)

    def __eq__(self, member):
        assert isinstance(member, Member)
        return self._public_key.__eq__(member._public_key)

    def __ne__(self, member):
        assert isinstance(member, Member)
        return self._public_key.__ne__(member._public_key)

    def __cmp__(self, member):
        assert isinstance(member, Member)
        return self._public_key.__cmp__(member._public_key)

    def __hash__(self):
        """
        Allows Member classes to be used as keys in a dictionary.
        """
        return self._public_key.__hash__()

    def __str__(self):
        """
        Returns a human readable string representing the member.
        """
        return "<%s %d %s>" % (self.__class__.__name__, self._database_id, self._mid.encode("HEX"))

class PrivateMember(Private, Member):
    def __init__(self, public_key, private_key=None, sync_with_database=True):
        assert isinstance(public_key, str)
        assert not public_key.startswith("-----BEGIN")
        assert isinstance(private_key, (type(None), str))
        assert private_key is None or not private_key.startswith("-----BEGIN")
        assert isinstance(sync_with_database, bool)

        if sync_with_database:
            if private_key is None:
                # get private key
                database = DispersyDatabase.get_instance()
                try:
                    private_key = str(database.execute(u"SELECT private_key FROM key WHERE public_key == ? LIMIT 1", (buffer(public_key),)).next()[0])
                except StopIteration:
                    pass

            else:
                # set private key
                database = DispersyDatabase.get_instance()
                database.execute(u"INSERT OR IGNORE INTO key(public_key, private_key) VALUES(?, ?)", (buffer(public_key), buffer(private_key)))

        if private_key is None:
            raise ValueError("The private key is unavailable")

        super(PrivateMember, self).__init__(public_key, ec_from_private_bin(private_key), sync_with_database)
        self._private_key = private_key

    @property
    def private_key(self):
        return self._private_key

    def sign(self, data, offset=0, length=0):
        """
        Sign DATA using our private key.  Returns the signature.
        """
        assert not self._private_key is None
        return ec_sign(self._ec, sha1(data[offset:length or len(data)]).digest())

class MasterMember(Member):
    pass

class ElevatedMasterMember(MasterMember, PrivateMember):
    pass

class MyMember(PrivateMember):
    pass

if __debug__:
    if __name__ == "__main__":
        from crypto import ec_generate_key, ec_to_public_bin, ec_to_private_bin

        ec = ec_generate_key(u"low")
        public_key = ec_to_public_bin(ec)
        private_key = ec_to_private_bin(ec)
        public_member = Member(public_key, sync_with_database=False)
        private_member = PrivateMember(public_key, private_key, sync_with_database=False)

        data = "Hello World! " * 1000
        sig = private_member.sign(data)
        digest = sha1(data).digest()
        dprint(sig.encode("HEX"))
        assert public_member.verify(data, sig)
        assert private_member.verify(data, sig)
