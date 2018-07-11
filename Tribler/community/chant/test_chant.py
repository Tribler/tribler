from pony import orm
from pony.orm import db_session
import os

import Tribler.community.chant.testtools as tt
from Tribler.community.chant.MDPackXDR import REGULAR_TORRENT
from Tribler.community.chant.chant import *
from Tribler.Test.test_as_server import TestAsServer
from Tribler.community.chant.orm import start_orm, db

db_filename = ":memory:"
start_orm(db_filename, create_db=True)


class TestChant(TestAsServer):

    def setUpPreSession(self):
        super(TestChant, self).setUpPreSession()
        self.config.set_libtorrent_enabled(True)

    def setUp(self):
        super(TestChant, self).setUp()
        self.maxDiff = None
        self.crypto = tt.crypto
        self.key = tt.key
        self.public_key = tt.public_key
        self.md_dict_list = [tt.get_regular_md_dict(n) for n in range(0, 5)]
        # db_filename = os.path.abspath(os.path.join(self.testdir, "chant.db"))
        self.testdir = self.session.config.get_state_dir()
        self.channels_dir = os.path.abspath(os.path.join(self.testdir, "channels"))

    @db_session
    def CleanDB(self):
        db.execute("DELETE from PeerORM")
        db.execute("DELETE from MetadataGossip")
        db.execute("DELETE from FtsIndex")

    def tearDown(self):
        super(TestChant, self).tearDown()
        self.CleanDB()

    @db_session
    def CreateChanSnippet(self):
        title = "Channel 1"
        for md_dict in self.md_dict_list:
            create_metadata_gossip(key=self.key, md_dict=md_dict)
        md_list = orm.select(g for g in MetadataGossip)[:]

        chan = create_channel(self.key, title, self.channels_dir, add_list=md_list, tags="some.tags")
        return chan

    @db_session
    def CreateUpdatedChanSnippet(self):
        chan = self.CreateChanSnippet()
        chan_dir = os.path.abspath(os.path.join(self.channels_dir, chan.title))

        remove_list = list_channel(chan)[-2:]
        new_md_dict = remove_list[0].to_dict()
        new_md_dict['title'] = new_md_dict['title'] + str(' new version')
        new_md_dict.pop('rowid')
        new_md = create_metadata_gossip(key=self.key, md_dict=new_md_dict)

        md_list = orm.select(g for g in MetadataGossip if
                             g.public_key == chan.public_key and
                             g.type == REGULAR_TORRENT and g.rowid !=
                             remove_list[0].rowid)[:]
        md_preupdate_list = [md.to_dict() for md in md_list]

        chan_updated = update_channel(self.key, chan, self.channels_dir, add_list=[new_md], remove_list=remove_list)

        return (md_preupdate_list, chan, chan_updated)

    @db_session
    def TestCreateMetadataGossip(self):
        for md_dict in self.md_dict_list:
            create_metadata_gossip(key=self.key, md_dict=md_dict)

        md_list = orm.select(g for g in MetadataGossip)[:]
        restored_dict_list = [md.to_dict() for md in md_list]

        for i in range(len(self.md_dict_list)):
            orig = serialize_metadata_gossip(self.md_dict_list[i])
            from_db = serialize_metadata_gossip(restored_dict_list[i])
            self.assertEqual(orig, from_db)

    @db_session
    def TestCreateChannel(self):
        chan = self.CreateChanSnippet()
        self.assertEqual(chan.type, CHANNEL_TORRENT)
        self.assertEqual(chan.public_key, buffer(self.public_key))

        md_list = orm.select(g for g in MetadataGossip)[:]
        self.assertEqual(len(md_list), len(self.md_dict_list) + 1)

        self.assertEqual(len(list_channel(chan)), chan.version)

        return

    @db_session
    def TestProcessChannelDir(self):
        chan = self.CreateChanSnippet()
        self.CleanDB()
        chan_dir = os.path.abspath(os.path.join(self.channels_dir, chan.title))

        process_channel_dir(chan_dir)
        md_list = list_channel(chan)
        self.assertEqual(len(md_list), chan.version)

        for i in range(len(self.md_dict_list)):
            orig = serialize_metadata_gossip(self.md_dict_list[i])
            from_db = serialize_metadata_gossip(md_list[i].to_dict())
            self.assertEqual(orig, from_db)

    @db_session
    def TestUpdateChannel(self):
        md_preupdate_list, _, chan_updated = self.CreateUpdatedChanSnippet()

        md_postupdate_list = [md.to_dict() for md in list_channel(chan_updated)]
        self.assertEqual(len(md_preupdate_list) - 1, len(md_postupdate_list))
        for i in range(len(md_postupdate_list) - 1):
            self.assertDictEqual(md_preupdate_list[i], md_postupdate_list[i])

    @db_session
    def TestLoadUpdatedChannel(self):
        _, _, chan_updated = self.CreateUpdatedChanSnippet()
        md_postupdate_list = [md.to_dict() for md in list_channel(chan_updated)]
        chan_dir = os.path.abspath(os.path.join(self.channels_dir, chan_updated.title))
        self.CleanDB()

        process_channel_dir(chan_dir)
        md_postload_list = [md.to_dict() for md in list_channel(chan_updated)]
        self.assertEqual(len(md_postload_list), len(md_postupdate_list))
        for i, _ in enumerate(md_postupdate_list):
            orig = serialize_metadata_gossip(md_postupdate_list[i])
            from_db = serialize_metadata_gossip(md_postload_list[i])
            self.assertEqual(orig, from_db)

    @db_session
    def TestFts(self):
        def Search(query):
            return MetadataGossip.search_keyword(query)[:]

        for md_dict in self.md_dict_list:
            create_metadata_gossip(key=self.key, md_dict=md_dict)
        self.assertEqual(1, len(Search("Torrent1")))
        self.assertEqual(len(self.md_dict_list), len(Search("Regular")))
        self.assertEqual(len(self.md_dict_list), len(Search("Regularity")))
        self.assertEqual(5, len(Search("tag1")))
        self.assertEqual(1, len(Search("Regular AND Torrent1")))
        self.assertEqual(2, len(Search("Torrent1 OR Torrent2")))
