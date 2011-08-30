# Python 2.5 features
from __future__ import with_statement

from hashlib import sha1

from singleton import Parameterized1Singleton
from dispersydatabase import DispersyDatabase
from crypto import ec_from_private_bin, ec_from_public_bin, ec_to_public_bin, ec_signature_length, ec_verify, ec_sign

if __debug__:
    from dprint import dprint
    from crypto import ec_check_public_bin, ec_check_private_bin

class Member(Parameterized1Singleton):
    """
    The Member class represents a single member in the Dispersy database.

    Each Member instance must be created or retrieved using has_instance or get_instance methods.

    - instances that have a public_key can verify signatures.

    - instances that have a private_key can both verify and sign data.

    - instances that have neither a public_key nor a private key are special cases and are indexed
      using the sha1 digest of the public key, supplied by some external party.
    """

    def __new__(cls, public_key, private_key="", sync_with_database=True, public_key_available=True):
        """
        Some member instances may be indexed using the sha1 digest instead of the public key.

        we must check if this new instance replaces a previously made instance.
        """
        assert isinstance(public_key, str)
        assert isinstance(private_key, str)
        assert isinstance(sync_with_database, bool)
        assert isinstance(public_key_available, bool)
        assert (public_key_available and len(public_key) > 0 and not public_key.startswith("-----BEGIN")) or \
               (not public_key_available and len(public_key) == 20), (len(public_key), public_key_available, public_key.encode("HEX"))
        assert (public_key_available and len(private_key) > 0 and not private_key.startswith("-----BEGIN")) or len(private_key) == 0
        if public_key_available:
            # determine if there already was a member with this mid (given the known public key)
            mid = sha1(public_key).digest()
            member = cls.has_instance(mid)
            if member:
                # TODO we might want to remove the old singleton link (indexed by mid), however, we
                # need to force the issue since it is currently not allowed as there are still
                # references to it
                if __debug__: dprint("singleton fix!", force=1)
                return member

        else:
            # determine if there already was a member with this public key (given the known mid)
            for member in cls.get_instances():
                # note that public_key, in this case, contains the mid
                if member.mid == public_key:
                    if __debug__: dprint("singleton fix", force=1)
                    return member

        return super(Member, cls).__new__(cls)#, public_key, private_key, sync_with_database, public_key_available)

    def __init__(self, public_key, private_key="", sync_with_database=True, public_key_available=True):
        """
        Create a new Member instance.  Member instances must be reated or retrieved using
        has_instance or get_instance.

        To create a Member instance we either need a public_key or a mid.  If only the mid is
        available it must be given as the public_key parameter and public_key_available must be
        False.  In this case the member will be unable to verify or sign data.

        Also not that it is possible, however unlikely, that someone is able to find another member
        with the same mid.  This will cause conflicts until the public_key is available.
        """
        assert isinstance(public_key, str)
        assert isinstance(private_key, str)
        assert isinstance(sync_with_database, bool)
        assert isinstance(public_key_available, bool)
        assert (public_key_available and len(public_key) > 0 and not public_key.startswith("-----BEGIN")) or \
               (not public_key_available and len(public_key) == 20), (len(public_key), public_key_available, public_key.encode("HEX"))
        assert (public_key_available and len(private_key) > 0 and not private_key.startswith("-----BEGIN")) or len(private_key) == 0

        database = DispersyDatabase.get_instance()

        if hasattr(self, "_database_id"):
            #
            # singleton already exists.  we may have received a public or private key now, so update
            # those in the database is needed
            #
            if __debug__: dprint("continue with existing singleton", force=1)

            if public_key_available:
                assert self._public_key == "" or self._public_key == public_key
                assert self._private_key == "" or self._private_key == private_key

                if not self._public_key:
                    assert public_key
                    assert ec_check_public_bin(public_key), public_key.encode("HEX")
                    self._public_key = public_key
                    if sync_with_database:
                        database.execute(u"UPDATE member SET public_key = ? WHERE id = ?", (buffer(public_key), self._database_id))

                if not self._private_key:
                    assert private_key
                    assert ec_check_private_bin(private_key), private_key.encode("HEX")
                    self._private_key = private_key
                    if sync_with_database:
                        database.execute(u"UPDATE private_key SET private_key = ? WHERE member = ?", (buffer(private_key), self._database_id))

                self._ec = ec_from_private_bin(self._private_key) if self._private_key else ec_from_public_bin(self._public_key)
                self._signature_length = ec_signature_length(self._ec)

            else:
                # we have nothing new
                pass

        else:
            #
            # singleton did not exist.  we make a new one
            #
            if public_key_available:
                assert public_key
                assert ec_check_public_bin(public_key), public_key.encode("HEX")
                assert not private_key or ec_check_private_bin(private_key), private_key.encode("HEX")
                self._public_key = public_key
                self._private_key = private_key
                self._mid = sha1(public_key).digest()
                self._database_id = -1
                self._address = ("", -1)
                self._tags = []

                if sync_with_database:
                    try:
                        self._database_id, private_key = database.execute(u"SELECT m.id, p.private_key FROM member AS m LEFT OUTER JOIN private_key AS p ON p.member = m.id WHERE m.public_key = ? LIMIT 1",
                                                                 (buffer(self._public_key),)).next()
                    except StopIteration:
                        # TODO check if there is a member already in the database where we only had
                        # the MID

                        database.execute(u"INSERT INTO member(mid, public_key) VALUES(?, ?)", (buffer(self._mid), buffer(self._public_key)))
                        self._database_id = database.last_insert_rowid
                        dprint("INSERT INTO member... ", self._database_id, " ", id(self), " ", self._mid.encode("HEX"), force=1)

                    else:
                        if not self._private_key and private_key:
                            self._private_key = str(private_key)

                self._ec = ec_from_private_bin(self._private_key) if self._private_key else ec_from_public_bin(self._public_key)
                self._signature_length = ec_signature_length(self._ec)

            else:
                assert len(public_key) == 20, public_key.encode("HEX")
                self._public_key = ""
                self._private_key = ""
                self._mid = public_key
                self._database_id = -1
                self._address = ("", -1)
                self._tags = []

                if sync_with_database:
                    try:
                        # # TODO do something smart to select the right mid (multiple can exist...)
                        self._database_id, = database.execute(u"SELECT id FROM member WHERE mid = ? LIMIT 1",
                                                              (buffer(self._mid),)).next()
                    except StopIteration:
                        database.execute(u"INSERT INTO member(mid) VALUES(?)", (buffer(self._mid),))
                        self._database_id = database.last_insert_rowid

                self._ec = None
                self._signature_length = 0

        if sync_with_database:
            self.update()

        if __debug__: dprint("mid:", self._mid.encode("HEX"), " db:", self._database_id, " public:", bool(self._public_key), " private:", bool(self._private_key), " from-public:", public_key_available)

    def update(self):
        """
        Update tag and addresses from the database.
        """
        execute = DispersyDatabase.get_instance().execute

        # set tags
        try:
            tags, = execute(u"SELECT tags FROM member WHERE id = ?", (self._database_id,)).next()
        except StopIteration:
            assert False, "should never occur"
        else:
            self._tags = [tag for tag in tags.split(",") if tag]
            if __debug__:
                assert len(set(self._tags)) == len(self._tags), ("there are duplicate tags", self._tags)
                for tag in self._tags:
                    assert tag in (u"store", u"ignore", u"blacklist"), tag

        for community, host, port in execute(u"SELECT community, host, port FROM identity WHERE member = ?", (self._database_id,)):
            # TODO we may have multiple addresses
            self._address = (str(host), port)

    @property
    def mid(self):
        """
        The member id.  This is the 20 byte sha1 hash over the public key.
        """
        return self._mid

    @property
    def public_key(self):
        """
        The public key.

        This is binary representation of the public key.

        It may be an empty string when the public key is not yet available.  In this case the verify
        method will always return False and the sign method will raise a RuntimeException.
        """
        return self._public_key

    @property
    def private_key(self):
        """
        The private key.

        This is binary representation of the private key.

        It may be an empty string when the private key is not yet available.  In this case the sign
        method will raise a RuntimeException.
        """
        return self._private_key

    @property
    def signature_length(self):
        """
        The length, in bytes, of a signature.
        """
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
        assert tag in [u"store", u"ignore", u"blacklist"]
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

        execute = DispersyDatabase.get_instance().execute
        execute(u"UPDATE member SET tags = ? WHERE id = ?", (u",".join(sorted(self._tags)), self._database_id))
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
    def __get_must_blacklist(self):
        return u"blacklist" in self._tags
    # @must_blacklist.setter
    def __set_must_blacklist(self, value):
        return self._set_tag(u"blacklist", value)
    # .setter was introduced in Python 2.6
    must_blacklist = property(__get_must_blacklist, __set_must_blacklist)

    def verify(self, data, signature, offset=0, length=0):
        """
        Verify that DATA, starting at OFFSET up to LENGTH bytes, was signed by this member and
        matches SIGNATURE.

        DATA is the signed data and the signature concatenated.
        OFFSET is the offset for the signed data.
        LENGTH is the length of the signature and the data, in bytes.

        Returns True or False.
        """
        assert isinstance(data, str)
        assert isinstance(signature, str)
        assert isinstance(offset, (int, long))
        assert isinstance(length, (int, long))
        length = length or len(data)
        return self._public_key and \
               self._signature_length == len(signature) \
               and ec_verify(self._ec, sha1(data[offset:offset+length]).digest(), signature)

    def sign(self, data, offset=0, length=0):
        """
        Returns the signature of DATA, starting at OFFSET up to LENGTH bytes.

        Will raise a RuntimeException when this we do not have the private key.
        """
        if self._private_key:
            return ec_sign(self._ec, sha1(data[offset:length or len(data)]).digest())
        else:
            raise RuntimeException("unable to sign data without the private key")

    def __eq__(self, member):
        assert isinstance(member, Member)
        return self._public_key.__eq__(member._public_key)

    def __ne__(self, member):
        assert isinstance(member, Member)
        return self._public_key.__ne__(member._public_key)

    def __cmp__(self, member):
        assert isinstance(member, Member)
        return cmp(self._public_key, member._public_key)

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
