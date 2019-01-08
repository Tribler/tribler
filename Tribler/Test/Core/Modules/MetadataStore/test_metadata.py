import os

from pony import orm
from pony.orm import db_session
from twisted.internet.defer import inlineCallbacks

from Tribler.Core.Modules.MetadataStore.serialization import MetadataPayload, KeysMismatchException
from Tribler.Core.Modules.MetadataStore.store import MetadataStore
from Tribler.Test.Core.base_test import TriblerCoreTest
from Tribler.pyipv8.ipv8.keyvault.crypto import default_eccrypto


class TestMetadata(TriblerCoreTest):
    """
    Contains various tests for the Metadata type.
    """

    @inlineCallbacks
    def setUp(self):
        yield super(TestMetadata, self).setUp()
        self.my_key = default_eccrypto.generate_key(u"curve25519")
        self.mds = MetadataStore(os.path.join(self.session_base_dir, 'test.db'), self.session_base_dir,
                                 self.my_key)

    @inlineCallbacks
    def tearDown(self):
        self.mds.shutdown()
        yield super(TestMetadata, self).tearDown()

    @db_session
    def test_to_dict(self):
        """
        Test whether converting metadata to a dictionary works
        """
        metadata = self.mds.Metadata.from_dict({})
        self.assertTrue(metadata.to_dict())

    @db_session
    def test_serialization(self):
        """
        Test converting metadata to serialized data and back
        """
        metadata1 = self.mds.Metadata.from_dict({})
        serialized1 = metadata1.serialized()
        metadata1.delete()

        metadata2 = self.mds.Metadata.from_payload(MetadataPayload.from_signed_blob(serialized1))
        serialized2 = metadata2.serialized()
        self.assertEqual(serialized1, serialized2)

    @db_session
    def test_key_mismatch_exception(self):
        mismatched_key = default_eccrypto.generate_key(u"curve25519")
        metadata = self.mds.Metadata.from_dict({})
        self.assertRaises(KeysMismatchException, metadata.serialized, key=mismatched_key)

    @db_session
    def test_to_file(self):
        """
        Test writing metadata to a file
        """
        metadata = self.mds.Metadata.from_dict({})
        file_path = os.path.join(self.session_base_dir, 'metadata.file')
        metadata.to_file(file_path)
        self.assertTrue(os.path.exists(file_path))

    @db_session
    def test_has_valid_signature(self):
        """
        Test whether a signature can be validated correctly
        """
        metadata = self.mds.Metadata.from_dict({})
        self.assertTrue(metadata.has_valid_signature())

        saved_key = metadata.public_key
        # Mess with the public key
        metadata.public_key = 'a'
        self.assertFalse(metadata.has_valid_signature())

        # Mess with the signature
        metadata.public_key = saved_key
        metadata.signature = 'a'
        self.assertFalse(metadata.has_valid_signature())

    @db_session
    def test_from_payload(self):
        """
        Test converting a metadata payload to a metadata object
        """
        metadata = self.mds.Metadata.from_dict({})
        metadata_dict = metadata.to_dict()
        metadata.delete()
        metadata_payload = MetadataPayload(**metadata_dict)
        self.assertTrue(self.mds.Metadata.from_payload(metadata_payload))
