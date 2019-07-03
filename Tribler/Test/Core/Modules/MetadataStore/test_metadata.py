from __future__ import absolute_import

import os
from binascii import hexlify

from ipv8.database import database_blob
from ipv8.keyvault.crypto import default_eccrypto

from pony import orm
from pony.orm import db_session

from twisted.internet.defer import inlineCallbacks

from Tribler.Core.Modules.MetadataStore.serialization import (
    CHANNEL_NODE, ChannelNodePayload, KeysMismatchException, NULL_KEY, NULL_SIG)
from Tribler.Core.Modules.MetadataStore.store import MetadataStore
from Tribler.Core.exceptions import InvalidChannelNodeException, InvalidSignatureException
from Tribler.Test.Core.base_test import TriblerCoreTest


class TestMetadata(TriblerCoreTest):
    """
    Contains various tests for the ChannelNode type.
    """

    @inlineCallbacks
    def setUp(self):
        yield super(TestMetadata, self).setUp()
        self.my_key = default_eccrypto.generate_key(u"curve25519")
        self.mds = MetadataStore(':memory:', self.session_base_dir, self.my_key)

    @inlineCallbacks
    def tearDown(self):
        self.mds.shutdown()
        yield super(TestMetadata, self).tearDown()

    @db_session
    def test_to_dict(self):
        """
        Test whether converting metadata to a dictionary works
        """
        metadata = self.mds.ChannelNode.from_dict({})
        self.assertTrue(metadata.to_dict())

    @db_session
    def test_serialization(self):
        """
        Test converting metadata to serialized data and back
        """
        metadata1 = self.mds.ChannelNode.from_dict({})
        serialized1 = metadata1.serialized()
        metadata1.delete()
        orm.flush()

        metadata2 = self.mds.ChannelNode.from_payload(ChannelNodePayload.from_signed_blob(serialized1)[0])
        serialized2 = metadata2.serialized()
        self.assertEqual(serialized1, serialized2)

        # Test no signature exception
        metadata2_dict = metadata2.to_dict()
        metadata2_dict.pop("signature")
        self.assertRaises(InvalidSignatureException, ChannelNodePayload, **metadata2_dict)

        serialized3 = serialized2[:-5] + "\xee" * 5
        self.assertRaises(InvalidSignatureException, ChannelNodePayload.from_signed_blob, serialized3)
        # Test bypass signature check
        ChannelNodePayload.from_signed_blob(serialized3, check_signature=False)

    @db_session
    def test_ffa_serialization(self):
        """
        Test converting free-for-all (unsigned) torrent metadata to payload and back
        """
        metadata1 = self.mds.ChannelNode.from_dict({"public_key": "", "id_": "123"})
        serialized1 = metadata1.serialized()
        # Make sure sig is really zeroes
        self.assertTrue(hexlify(serialized1).endswith(hexlify(NULL_SIG)))
        metadata1.delete()
        orm.flush()

        metadata2 = self.mds.ChannelNode.from_payload(ChannelNodePayload.from_signed_blob(serialized1)[0])
        serialized2 = metadata2.serialized()
        self.assertEqual(serialized1, serialized2)

        # Check that it is impossible to create FFA node without specifying id_
        self.assertRaises(InvalidChannelNodeException, self.mds.ChannelNode.from_dict, {"public_key": ""})
        # Check that it is impossible to create FFA payload with non-null signature
        self.assertRaises(InvalidSignatureException, ChannelNodePayload, CHANNEL_NODE, 0, NULL_KEY, 0, 0, 0,
                          signature="123")
        # Check that creating a pair of metadata entries do not trigger uniqueness constraints error
        self.mds.ChannelNode.from_dict({"public_key": "", "id_": "124"})
        self.mds.ChannelNode.from_dict({"public_key": "", "id_": "125"})

    @db_session
    def test_key_mismatch_exception(self):
        mismatched_key = default_eccrypto.generate_key(u"curve25519")
        metadata = self.mds.ChannelNode.from_dict({})
        self.assertRaises(KeysMismatchException, metadata.serialized, key=mismatched_key)

    @db_session
    def test_to_file(self):
        """
        Test writing metadata to a file
        """
        metadata = self.mds.ChannelNode.from_dict({})
        file_path = os.path.join(self.session_base_dir, 'metadata.file')
        metadata.to_file(file_path)
        self.assertTrue(os.path.exists(file_path))

    @db_session
    def test_has_valid_signature(self):
        """
        Test whether a signature can be validated correctly
        """
        metadata = self.mds.ChannelNode.from_dict({})
        self.assertTrue(metadata.has_valid_signature())

        md_dict = metadata.to_dict()

        # Mess with the signature
        metadata.signature = 'a'
        self.assertFalse(metadata.has_valid_signature())

        # Create metadata with wrong key
        metadata.delete()
        md_dict.update(public_key=database_blob("aaa"))
        md_dict.pop("rowid")

        metadata = self.mds.ChannelNode(skip_key_check=True, **md_dict)
        self.assertFalse(metadata.has_valid_signature())

        key = default_eccrypto.generate_key(u"curve25519")
        metadata2 = self.mds.ChannelNode(sign_with=key, **md_dict)
        self.assertTrue(database_blob(key.pub().key_to_bin()[10:]), metadata2.public_key)
        md_dict2 = metadata2.to_dict()
        md_dict2["signature"] = md_dict["signature"]
        self.assertRaises(InvalidSignatureException, self.mds.ChannelNode, **md_dict2)

    @db_session
    def test_from_payload(self):
        """
        Test converting a metadata payload to a metadata object
        """
        metadata = self.mds.ChannelNode.from_dict({})
        metadata_dict = metadata.to_dict()
        metadata.delete()
        orm.flush()
        metadata_payload = ChannelNodePayload(**metadata_dict)
        self.assertTrue(self.mds.ChannelNode.from_payload(metadata_payload))
