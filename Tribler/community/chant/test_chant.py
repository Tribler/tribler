import unittest

from pony import orm
from pony.orm import db_session
import os

import Tribler.community.chant.testtools as tt
from Tribler.community.chant.MDPackXDR import REGULAR_TORRENT
from Tribler.community.chant.chant import *
from Tribler.Test.test_as_server import TestAsServer
from Tribler.community.chant.orm import start_orm



class TestChant(TestAsServer):

    def setUpPreSession(self):
        super(TestChant, self).setUpPreSession()
        self.config.set_libtorrent_enabled(True)


    def TestCreateChannel(self):
        self.testdir = self.session.config.get_state_dir()
        db_filename = os.path.abspath(os.path.join(self.testdir, "chant.db"))
        start_orm(db_filename)
        self.run_db_session()

    @db_session
    def run_db_session(self):
        channels_dir = os.path.abspath(os.path.join(self.testdir, "channels"))
        self.maxDiff = None
        self.md_dict_list = [tt.get_regular_md_dict(n) for n in range(0, 5)]
        self.crypto = tt.crypto
        self.key = tt.key
        self.public_key = tt.public_key
        # Test create_metadata_gossip
        for md_dict in self.md_dict_list:
            create_metadata_gossip(key=self.key, md_dict=md_dict)

        md_list = orm.select(g for g in MetadataGossip)[:]
        restored_dict_list = [md.to_dict() for md in md_list]

        for i in range(len(self.md_dict_list)):
            orig = serialize_metadata_gossip(self.md_dict_list[i])
            from_db = serialize_metadata_gossip(restored_dict_list[i])
            self.assertEqual(orig, from_db)

        # Test create_channel
        title = "Channel 1"
        md_list = orm.select(g for g in MetadataGossip)[:]

        chan = create_channel(self.key, title, channels_dir, add_list=md_list, tags="some.tags")
        self.assertEqual(chan.type, CHANNEL_TORRENT)
        self.assertEqual(chan.public_key, buffer(self.public_key))

        md_list = orm.select(g for g in MetadataGossip)[:]
        self.assertEqual(len(md_list), len(self.md_dict_list) + 1)

        md_list = orm.select(g for g in MetadataGossip if
                             g.public_key == chan.public_key and
                             g.type == REGULAR_TORRENT)[:]
        print md_list
        self.assertEqual(len(md_list), chan.version)

        # Test process_channel_dir
        for md in md_list:
            md.delete()
        chan_dir = os.path.abspath(os.path.join(channels_dir, chan.title))
        process_channel_dir(chan_dir)
        md_list = orm.select(g for g in MetadataGossip if
                             g.public_key == chan.public_key and
                             g.type == REGULAR_TORRENT)[:]
        print md_list
        self.assertEqual(len(md_list), chan.version)

        for i in range(len(self.md_dict_list)):
            orig = serialize_metadata_gossip(self.md_dict_list[i])
            from_db = serialize_metadata_gossip(md_list[i].to_dict())
            self.assertEqual(orig, from_db)

        # Test update_channel
        remove_list = md_list[-2:]
        new_md_dict = remove_list[0].to_dict()
        new_md_dict['title'] = new_md_dict['title'] + str(' new version')
        new_md_dict.pop('id')
        new_md = create_metadata_gossip(key=self.key, md_dict=new_md_dict)

        md_list = orm.select(g for g in MetadataGossip if
                             g.public_key == chan.public_key and
                             g.type == REGULAR_TORRENT and g.id != remove_list[0].id)[:]
        md_preupdate_list = [md.to_dict() for md in md_list]

        chan_updated = update_channel(self.key, chan, channels_dir, add_list=[new_md], remove_list=remove_list)

        md_list = orm.select(g for g in MetadataGossip if
                             g.public_key == chan_updated.public_key and
                             g.type == REGULAR_TORRENT)[:]
        md_postupdate_list = [md.to_dict() for md in md_list]
        self.assertEqual(len(md_preupdate_list) - 1, len(md_postupdate_list))
        for i in range(len(md_postupdate_list) - 1):
            self.assertDictEqual(md_preupdate_list[i], md_postupdate_list[i])

        # Test load updated torrent
        md_list = orm.select(g for g in MetadataGossip if
                             g.public_key == chan_updated.public_key and
                             g.type == REGULAR_TORRENT)[:]
        for md in md_list:
            md.delete()
        process_channel_dir(chan_dir)
        md_list = orm.select(g for g in MetadataGossip if
                             g.public_key == chan_updated.public_key and
                             g.type == REGULAR_TORRENT)[:]

        md_postload_list = [md.to_dict() for md in md_list]
        self.assertEqual(len(md_postload_list), len(md_postupdate_list))
        for i in range(len(md_postupdate_list)):
            orig = serialize_metadata_gossip(md_postupdate_list[i])
            from_db = serialize_metadata_gossip(md_postload_list[i])
            self.assertEqual(orig, from_db)
