import os
from datetime import datetime
import time

from pony import orm
from pony.orm import db_session

from Tribler.Core.Modules.MetadataStore.channels import process_channel_dir, create_channel_torrent
from Tribler.Test.Core.Modules.MetadataStore import tools as tt
from Tribler.Test.Core.Modules.MetadataStore.tools import are_dir_trees_equal
from Tribler.Test.test_as_server import TestAsServer

TESTCHANNEL_DIR_NAME = u"b944df9bc5e7ae8f759960ac257eaa1f5ba499a7df5b38791fae5dc52ea7"


class TestChannelMD(TestAsServer):
    FILE_DIR = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
    TEST_FILES_DIR = os.path.abspath(os.path.join(
        FILE_DIR, u"../../data/MetadataStore/"))

    template = {
        "title": "",
        "infohash": "1" * 20,
        "torrent_date": datetime(1970, 1, 1),
        "tags": "video"}

    def test_create_channel_md(self):
        with db_session:
            self.session.mds.ChannelMD()
            self.assertEqual(
                orm.select(g for g in self.session.mds.ChannelMD).count(),
                1)

    def test_list_contents(self):
        with db_session:
            key1 = self.session.trustchain_keypair
            channel1 = self.session.mds.ChannelMD(
                public_key=key1.pub().key_to_bin())
            self.session.mds.TorrentMD.from_dict(key1, self.template)

            key2 = tt.key
            channel2 = self.session.mds.ChannelMD(
                public_key=key2.pub().key_to_bin())
            self.session.mds.TorrentMD.from_dict(key2, self.template)
            self.session.mds.TorrentMD.from_dict(key2, self.template)

            self.assertEqual(1, len(channel1.contents_list))
            self.assertEqual(2, len(channel2.contents_list))

    def test_list_new_entries(self):
        with db_session:
            key1 = self.session.trustchain_keypair
            md1 = self.session.mds.TorrentMD.from_dict(
                key1, dict(self.template, timestamp=datetime.utcnow()))
            # Windows does not provide microseconds resolution, so we have to sleep
            # to ensure there is some noticeable difference between timestamps
            time.sleep(0.1)
            channel1 = self.session.mds.ChannelMD(
                public_key=key1.pub().key_to_bin(),
                timestamp=datetime.utcnow())
            time.sleep(0.1)
            md2 = self.session.mds.TorrentMD.from_dict(
                key1, dict(self.template, timestamp=datetime.utcnow()))

            self.assertIn(md2, channel1.newer_entries)
            self.assertNotIn(md1, channel1.newer_entries)

    def test_garbage_collect(self):
        with db_session:
            key1 = self.session.trustchain_keypair
            del1 = self.session.mds.DeletedMD(
                public_key=key1.pub().key_to_bin(),
                timestamp=datetime.utcnow(),
                delete_signature="foo")
            time.sleep(0.1)
            channel1 = self.session.mds.ChannelMD(
                public_key=key1.pub().key_to_bin(),
                timestamp=datetime.utcnow())
            time.sleep(0.1)
            del2 = self.session.mds.DeletedMD(
                public_key=key1.pub().key_to_bin(),
                timestamp=datetime.utcnow(),
                delete_signature="foo")
            channel1.garbage_collect()

            del_entries = orm.select(g for g in self.session.mds.DeletedMD)[:]
            self.assertNotIn(del1, del_entries)
            self.assertIn(del2, del_entries)

    def test_from_dict(self):
        with db_session:
            key1 = self.session.trustchain_keypair
            d = tt.get_sample_channel_dict(key1)
            chan = self.session.mds.ChannelMD.from_dict(key1, d)
            self.assertDictContainsSubset(d, chan.to_dict())

    def test_update_metadata(self):
        with db_session:
            key1 = self.session.trustchain_keypair
            d = tt.get_sample_channel_dict(key1)
            chan = self.session.mds.ChannelMD.from_dict(key1, d)
            self.session.mds.TorrentMD.from_dict(key1, self.template)
            update_dict = {"tc_pointer": 222,
                           "tags": "eee",
                           "title": "qqq"}
            chan.update_metadata(key1, update_dict=update_dict)
            self.assertDictContainsSubset(update_dict, chan.to_dict())

    def test_commit_to_torrent_add_torrents(self):
        with db_session:
            key1 = self.session.trustchain_keypair
            d = tt.get_sample_channel_dict(key1)
            chan = self.session.mds.ChannelMD.from_dict(key1, d)
            md1 = self.session.mds.TorrentMD.from_dict(key1, self.template)
            chan.commit_to_torrent(key1, self.session.channels_dir, md_list=[md1])

            md2 = self.session.mds.TorrentMD.from_dict(key1, self.template)
            md1_orig = md1.to_dict()
            md2_orig = md2.to_dict()
            del md1_orig["addition_timestamp"]
            del md1_orig["rowid"]
            del md2_orig["addition_timestamp"]
            del md2_orig["rowid"]

            chan.commit_to_torrent(key1, self.session.channels_dir, md_list=[md2])

            md1.delete()
            md2.delete()
            process_channel_dir(self.session.mds,
                                os.path.join(self.session.channels_dir, chan.get_dirname))

            self.assertDictContainsSubset(
                md1_orig, chan.contents_list[0].to_dict())
            self.assertDictContainsSubset(
                md2_orig, chan.contents_list[1].to_dict())

    def test_commit_to_torrent_delete_torrents(self):
        with db_session:
            key1 = self.session.trustchain_keypair
            d = tt.get_sample_channel_dict(key1)
            chan = self.session.mds.ChannelMD.from_dict(key1, d)
            md1 = self.session.mds.TorrentMD.from_dict(key1, self.template)
            md2 = self.session.mds.TorrentMD.from_dict(key1, self.template)
            chan.commit_to_torrent(
                key1,
                self.session.channels_dir,
                md_list=[md1, md2])

            md_del = self.session.mds.DeletedMD.from_dict(
                key1, {"public_key": key1.pub().key_to_bin(), "delete_signature": md1.signature})
            chan.commit_to_torrent(
                key1,
                self.session.channels_dir,
                md_list=[md_del])

            process_channel_dir(self.session.mds,
                                os.path.join(self.session.channels_dir,
                                             chan.get_dirname))
            self.assertEqual(1, len(chan.contents_list))
            self.assertEqual(chan.contents_list[:][0].rowid, md2.rowid)

    def test_process_channel_dir(self):
        sample_channel_dir = os.path.abspath(
            os.path.join(self.TEST_FILES_DIR, TESTCHANNEL_DIR_NAME))

        with db_session:
            process_channel_dir(self.session.mds, sample_channel_dir)

            buf_list = [e.serialized() for e in orm.select(
                g for g in self.session.mds.SignedGossip)[:]]
            create_channel_torrent(
                self.session.channels_dir,
                TESTCHANNEL_DIR_NAME,
                buf_list,
                0)

        generated_channel_dir = os.path.abspath(os.path.join(
            self.session.channels_dir, TESTCHANNEL_DIR_NAME))
        self.assert_(
            are_dir_trees_equal(
                sample_channel_dir,
                generated_channel_dir),
                os.listdir(generated_channel_dir))

    def test_process_channel_dir_wrong_filename_ext(self):
        sample_channel_dir = os.path.abspath(
            os.path.join( self.TEST_FILES_DIR, u"./bad_channel_ext"))

        self.assertRaises(NameError, process_channel_dir, self.session.mds, sample_channel_dir)

    def test_process_channel_dir_wrong_filename_num(self):
        sample_channel_dir = os.path.abspath(
            os.path.join( self.TEST_FILES_DIR, u"./bad_channel_num"))

        self.assertRaises(NameError, process_channel_dir, self.session.mds, sample_channel_dir)

    def test_process_channel_dir_wrong_filename_negnum(self):
        sample_channel_dir = os.path.abspath(
            os.path.join( self.TEST_FILES_DIR, u"./bad_channel_negnum"))

        self.assertRaises(NameError, process_channel_dir, self.session.mds, sample_channel_dir)
