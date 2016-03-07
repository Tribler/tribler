import os
from ConfigParser import DEFAULTSECT
from tempfile import mkdtemp

import shutil
from nose.tools import raises

from Tribler.Core.Utilities.configparser import CallbackConfigParser
from Tribler.Core.exceptions import OperationNotPossibleAtRuntimeException
from Tribler.Test.Core.base_test import TriblerCoreTest


class TestConfigParser(TriblerCoreTest):

    FILE_DIR = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
    CONFIG_FILES_DIR = os.path.abspath(os.path.join(FILE_DIR, u"data/config_files/"))

    def test_configparser_config1(self):
        ccp = CallbackConfigParser()
        ccp.read_file(os.path.join(self.CONFIG_FILES_DIR, 'config1.conf'))

        self.assertEqual(ccp.get('general', 'version'), 11)
        self.assertTrue(ccp.get('search_community', 'enabled'))
        self.assertIsInstance(ccp.get('tunnel_community', 'socks5_listen_ports'), list)
        self.assertFalse(ccp.get('foo', 'bar'))

    def test_configparser_copy(self):
        ccp = CallbackConfigParser()
        ccp.read_file(os.path.join(self.CONFIG_FILES_DIR, 'config1.conf'))

        copy_ccp = ccp.copy()
        self.assertEqual(copy_ccp.get('general', 'version'), 11)
        self.assertTrue(copy_ccp.get('search_community', 'enabled'))

    def test_configparser_set_callback(self):

        def parser_callback(section, option, old_value, new_value):
            return True

        ccp = CallbackConfigParser()
        ccp.set_callback(parser_callback)
        ccp.read_file(os.path.join(self.CONFIG_FILES_DIR, 'config1.conf'))

        ccp.set('search_community', 'enabled', False)
        ccp.set('search_community', 'bar', 42)

        self.assertFalse(ccp.get('search_community', 'enabled'))
        self.assertEquals(ccp.get('search_community', 'bar'), 42)

    @raises(OperationNotPossibleAtRuntimeException)
    def test_configparser_false_callback(self):

        def parser_callback(section, option, old_value, new_value):
            return False

        ccp = CallbackConfigParser()
        ccp.read_file(os.path.join(self.CONFIG_FILES_DIR, 'config1.conf'))
        ccp.set_callback(parser_callback)
        ccp.set('search_community', 'enabled', False)

    def test_configparser_write_file(self):

        temp_dir = mkdtemp(suffix="_tribler_test_session")
        ccp = CallbackConfigParser()
        ccp.read_file(os.path.join(self.CONFIG_FILES_DIR, 'config1.conf'))

        new_path = os.path.join(temp_dir, 'config_new.conf')
        ccp.write_file(new_path)

        self.assertTrue(os.path.isfile(new_path))
        ccp.read_file(new_path)

        self.assertEqual(ccp.get('general', 'version'), 11)
        self.assertTrue(ccp.get('search_community', 'enabled'))
        self.assertIsInstance(ccp.get('tunnel_community', 'socks5_listen_ports'), list)
        self.assertFalse(ccp.get('foo', 'bar'))

        shutil.rmtree(unicode(temp_dir), ignore_errors=True)

    def test_configparser_write_file_defaults(self):

        temp_dir = mkdtemp(suffix="_tribler_test_session")
        ccp = CallbackConfigParser(defaults={'foo': 'bar'})

        new_path = os.path.join(temp_dir, 'config_new.conf')
        ccp.write_file(new_path)

        self.assertTrue(os.path.isfile(new_path))
        ccp.read_file(new_path)
        self.assertEqual(ccp.get('DEFAULT', 'foo'), 'bar')

        shutil.rmtree(unicode(temp_dir), ignore_errors=True)
