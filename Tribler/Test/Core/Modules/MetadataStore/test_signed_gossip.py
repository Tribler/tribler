from datetime import datetime

from pony import orm
from pony.orm import db_session
from twisted.internet.defer import inlineCallbacks

from Tribler.Core.Modules.MetadataStore.serialization import deserialize_metadata_gossip, DeserializationError, \
    SerializationError
from Tribler.Test.test_as_server import TestAsServer


class TestSignedGossip(TestAsServer):

    @inlineCallbacks
    def setUp(self):
        yield super(TestSignedGossip, self).setUp()
        key = self.session.trustchain_keypair
        self.d = db_session()
        self.d.__enter__()
        self.g = self.session.mds.SignedGossip.from_dict(key, {})

    def tearDown(self):
        self.d.__exit__()
        super(TestSignedGossip, self).tearDown()

    def test_create_signed_gossip(self):
        self.assertEqual(
            orm.select(g for g in self.session.mds.SignedGossip).count(), 1)

    def test_from_dict_and_serialize(self):
        with db_session:
            d = deserialize_metadata_gossip(self.g.serialized())
            self.assert_(d is not None)

    def test_fail_deserialize_on_wrong_pk(self):
        with db_session:
            self.g.public_key = "wrong pk"
            self.assertRaises(DeserializationError, deserialize_metadata_gossip, self.g.serialized())

    def test_fail_serialize_with_wrong_sig(self):
        with db_session:
            self.g.signature = "wrong sig"
            self.assertRaises(SerializationError, self.g.serialized, check_signature=True)

    def test_fail_deserialize_on_wrong_sig(self):
        with db_session:
            self.g.signature = "wrong sig"
            self.assertRaises(DeserializationError, deserialize_metadata_gossip, self.g.serialized())

    def test_fail_deserialize_on_wrong_content(self):
        with db_session:
            self.g.timestamp = datetime(1971, 1, 1)  # Wrong time
            self.assertRaises(DeserializationError, deserialize_metadata_gossip, self.g.serialized())
