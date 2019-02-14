from __future__ import absolute_import

import os

from pony.orm import db_session
from twisted.internet.defer import inlineCallbacks

from Tribler.Core.Modules.MetadataStore.store import MetadataStore
from Tribler.Core.Utilities.tracker_utils import MalformedTrackerURLException
from Tribler.Test.Core.base_test import TriblerCoreTest
from Tribler.pyipv8.ipv8.keyvault.crypto import default_eccrypto


class TestTrackerState(TriblerCoreTest):
    """
    Contains various tests for the TrackerState class.
    """
    @inlineCallbacks
    def setUp(self):
        yield super(TestTrackerState, self).setUp()
        self.my_key = default_eccrypto.generate_key(u"curve25519")
        self.mds = MetadataStore(":memory:", self.session_base_dir, self.my_key)

    @inlineCallbacks
    def tearDown(self):
        self.mds.shutdown()
        yield super(TestTrackerState, self).tearDown()

    @db_session
    def test_create_tracker_state(self):
        ts = self.mds.TrackerState(url='http://tracker.tribler.org:80/announce')
        self.assertEqual(list(self.mds.TrackerState.select())[0], ts)

    @db_session
    def test_canonicalize_tracker_state(self):
        ts = self.mds.TrackerState(url='http://tracker.tribler.org:80/announce/')
        self.assertEqual(self.mds.TrackerState.get(url='http://tracker.tribler.org/announce'), ts)

    @db_session
    def test_canonicalize_raise_on_malformed_url(self):
        self.assertRaises(MalformedTrackerURLException, self.mds.TrackerState,
                          url='udp://tracker.tribler.org/announce/')
