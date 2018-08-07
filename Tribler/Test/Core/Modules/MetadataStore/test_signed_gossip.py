from datetime import datetime

from pony import orm
from pony.orm import db_session

from Tribler.Core.Modules.MetadataStore.serialization import deserialize_metadata_gossip
from Tribler.Test.test_as_server import TestAsServer


class TestSignedGossip(TestAsServer):
    def test_create_signed_gossip(self):
        with db_session:
            self.session.mds.SignedGossip()
            self.assertEqual(
                orm.select(g for g in self.session.mds.SignedGossip).count(),
                1)

    def test_from_dict_and_serialize(self):
        with db_session:
            key = self.session.trustchain_keypair
            g = self.session.mds.SignedGossip.from_dict(key, {})
            d = deserialize_metadata_gossip(g.serialized())
            self.assert_(d is not None)

    def test_fail_deserialize_on_wrong_pk(self):
        with db_session:
            key = self.session.trustchain_keypair
            g = self.session.mds.SignedGossip.from_dict(key, {})
            g.public_key = "wrong pk"
            d = deserialize_metadata_gossip(g.serialized())
            self.assert_(d is None)

    def test_fail_deserialize_on_wrong_sig(self):
        with db_session:
            key = self.session.trustchain_keypair
            g = self.session.mds.SignedGossip.from_dict(key, {})
            g.signature = "wrong sig"
            d = deserialize_metadata_gossip(g.serialized())
            self.assert_(d is None)

    def test_fail_deserialize_on_wrong_content(self):
        with db_session:
            key = self.session.trustchain_keypair
            g = self.session.mds.SignedGossip.from_dict(key, {})
            g.timestamp = datetime(1971, 1, 1)  # Wrong time
            d = deserialize_metadata_gossip(g.serialized())
            self.assert_(d is None)
