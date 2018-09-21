# -*- coding: utf-8 -*-
from datetime import datetime

from pony import orm
from pony.orm import db_session

from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Test.common import TORRENT_UBUNTU_FILE
from Tribler.Test.test_as_server import TestAsServer
from Tribler.Test.Core.Modules.MetadataStore import tools as tt


class TestTorrentMD(TestAsServer):
    template = {
        "infohash": "",
        "torrent_date": datetime(1970, 1, 1),
        "tags": "video"}

    def test_create_torrent_md(self):
        with db_session:
            self.session.lm.mds.TorrentMD()
            self.assertEqual(
                orm.select(g for g in self.session.lm.mds.TorrentMD).count(),
                1)

    def test_create_from_tdef(self):
        with db_session:
            key = self.session.trustchain_keypair
            tdef = TorrentDef.load(TORRENT_UBUNTU_FILE)
            md = self.session.lm.mds.TorrentMD.from_tdef(key, tdef)
            orig = {
                "infohash": buffer(tdef.get_infohash()),
                "title": tdef.get_name_as_unicode(),
                "size": tdef.get_length(),
                "torrent_date": datetime.fromtimestamp(tdef.get_creation_date())}
            self.assertDictContainsSubset(orig, md.to_dict())

    def test_search_keyword(self):
        with db_session:
            key = self.session.trustchain_keypair
            md1 = self.session.lm.mds.TorrentMD.from_dict(
                key, dict(self.template, title="foo bar 123", tags="video"))
            md2 = self.session.lm.mds.TorrentMD.from_dict(
                key, dict(self.template, title="eee 123", tags="video"))
            self.session.lm.mds.TorrentMD.from_dict(
                key, dict(self.template, title="xoxoxo bar", tags="video"))
            self.session.lm.mds.TorrentMD.from_dict(
                key, dict(self.template, title="xoxoxo bar", tags="audio"))
            self.assertEqual(
                md1.rowid,
                self.session.lm.mds.TorrentMD.search_keyword("foo")[0].rowid)
            self.assertEqual(
                md2.rowid,
                self.session.lm.mds.TorrentMD.search_keyword("eee")[0].rowid)
            self.assertEqual(
                2, len(
                    self.session.lm.mds.TorrentMD.search_keyword("123")))
            self.assertEqual(
                3, len(
                    self.session.lm.mds.TorrentMD.search_keyword("video")))

    def test_search_keyword_unicode(self):
        with db_session:
            key = self.session.trustchain_keypair
            md1 = self.session.lm.mds.TorrentMD.from_dict(
                key, dict(self.template, title=u"я маленький апельсин"))
            self.assertEqual(1, len(self.session.lm.mds.TorrentMD.search_keyword(u"маленький")))

    def test_search_keyword_wildcard(self):
        with db_session:
            key = self.session.trustchain_keypair
            md1 = self.session.lm.mds.TorrentMD.from_dict(
                key, dict(self.template, title="foobar 123"))
            md2 = self.session.lm.mds.TorrentMD.from_dict(
                key, dict(self.template, title="foobla 123"))
            self.assertEqual(0, len(self.session.lm.mds.TorrentMD.search_keyword("*")))
            self.assertEqual(1, len(self.session.lm.mds.TorrentMD.search_keyword("foobl*")))
            self.assertEqual(2, len(self.session.lm.mds.TorrentMD.search_keyword("foo*")))

    def test_search_keyword_sanitize(self):
        with db_session:
            key = self.session.trustchain_keypair
            md1 = self.session.lm.mds.TorrentMD.from_dict(
                key, dict(self.template, title="foobar 123"))
            self.assertEqual(0, len(self.session.lm.mds.TorrentMD.search_keyword("**")))
            self.assertEqual(0, len(self.session.lm.mds.TorrentMD.search_keyword("*.#@!%***$*.*")))

    def test_search_keyword_stemmed(self):
        with db_session:
            key = self.session.trustchain_keypair
            md = self.session.lm.mds.TorrentMD.from_dict(
                key, dict(self.template, title="mountains sheep", tags="video"))
            self.assertEqual(
                md.rowid,
                self.session.lm.mds.TorrentMD.search_keyword("mountain")[0].rowid)
            self.assertEqual(
                md.rowid,
                self.session.lm.mds.TorrentMD.search_keyword("sheeps")[0].rowid)

    def test_get_autocomplete_terms(self):
        with db_session:
            key = self.session.trustchain_keypair
            self.session.lm.mds.TorrentMD.from_dict(
                key, dict(self.template, title="mountains sheep", tags="video"))
            md = self.session.lm.mds.TorrentMD.from_dict(key, dict(
                self.template, title="regular sheepish guy", tags="video"))
            self.assertIn(
                'sheep',
                self.session.lm.mds.TorrentMD.getAutoCompleteTerms("shee", 10))
            self.assertIn(
                'sheepish',
                self.session.lm.mds.TorrentMD.getAutoCompleteTerms("shee", 10))

    def test_from_dict(self):
        with db_session:
            key1 = self.session.trustchain_keypair
            d = tt.get_sample_torrent_dict(key1)
            chan = self.session.lm.mds.TorrentMD.from_dict(key1, d)
            self.assertDictContainsSubset(d, chan.to_dict())
