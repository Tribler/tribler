from __future__ import absolute_import

import glob
import os
import pickle
from six.moves.configparser import RawConfigParser

from Tribler.Core.simpledefs import PERSISTENTSTATE_CURRENTVERSION


class PickleConverter(object):
    """
    This class is responsible for converting old .pickle files used for configuration files to a newer ConfigObj format.
    """

    def __init__(self, session):
        self.session = session

    def convert(self):
        """
        Calling this method will convert all configuration files to the ConfigObj.state format.
        """
        self.convert_session_config()
        self.convert_main_config()
        self.convert_download_checkpoints()

    def convert_session_config(self):
        """
        Convert the sessionconfig.pickle file to triblerd.conf. Do nothing if we do not have a pickle file.
        Remove the pickle file after we are done.
        """
        old_filename = os.path.join(self.session.config.get_state_dir(), 'sessconfig.pickle')

        if not os.path.exists(old_filename):
            return

        with open(old_filename, "rb") as old_file:
            sessconfig = pickle.load(old_file)

        # Upgrade to .state config
        new_config = self.session.config
        for key, value in sessconfig.iteritems():
            if key == 'minport':
                new_config.config['libtorrent']['port'] = value
            if key in ['state_dir', 'install_dir', 'eckeypairfilename', 'megacache']:
                new_config.config['general'][key] = value
            if key == 'mainline_dht':
                new_config.config['mainline_dht']['enabled'] = value
            if key == 'mainline_dht_port':
                new_config.config['mainline_dht']['port'] = value
            if key == 'torrent_checking':
                new_config.config['torrent_checking']['enabled'] = value
            if key in ['torrent_collecting', 'torrent_collecting_max_torrents', 'torrent_collecting_dir']:
                new_config.config['torrent_collecting']['enabled' if key == 'torrent_collecting' else key] = value
            if key in ['libtorrent', 'lt_proxytype', 'lt_proxyserver', 'lt_proxyauth']:
                new_config.config['libtorrent']['enabled' if key == 'libtorrent' else key] = value
            if key in ['dispersy_port', 'dispersy']:
                new_config.config['dispersy']['enabled' if key == 'dispersy' else 'port'] = value

        # Save the new file, remove the old one
        new_config.write()
        os.remove(old_filename)

    def convert_main_config(self):
        """
        Convert the abc.conf, user_download_choice.pickle, gui_settings and recent download history files
        to triblerd.conf.
        """
        new_config = self.session.config

        # Convert user_download_choice.pickle
        udcfilename = os.path.join(self.session.config.get_state_dir(), 'user_download_choice.pickle')
        if os.path.exists(udcfilename):
            with open(udcfilename, "r") as udc_file:
                choices = pickle.Unpickler(udc_file).load()
                choices = dict([(k.encode('hex'), v) for k, v in choices["download_state"].iteritems()])
                new_config.config['user_download_states'] = choices
                new_config.write()
            os.remove(udcfilename)

    def convert_download_checkpoints(self):
        """
        Convert all pickle download checkpoints to .state files.
        """
        checkpoint_dir = self.session.get_downloads_pstate_dir()

        filelist = os.listdir(checkpoint_dir)
        if not any([filename.endswith('.pickle') for filename in filelist]):
            return

        if os.path.exists(checkpoint_dir):
            for old_filename in glob.glob(os.path.join(checkpoint_dir, '*.pickle')):
                try:
                    with open(old_filename, "rb") as old_file:
                        old_checkpoint = pickle.load(old_file)
                except (EOFError, KeyError):
                    # Pickle file appears to be corrupted, remove it and continue
                    os.remove(old_filename)
                    continue

                new_checkpoint = RawConfigParser()
                new_checkpoint.add_section('downloadconfig')
                new_checkpoint.add_section('state')
                for key, value in old_checkpoint['dlconfig'].iteritems():
                    if key in ['saveas', 'max_upload_rate', 'max_download_rate', 'super_seeder', 'mode',
                               'selected_files', 'correctedfilename']:
                        new_checkpoint.set('downloadconfig', key, value)
                new_checkpoint.set('state', 'version', PERSISTENTSTATE_CURRENTVERSION)
                new_checkpoint.set('state', 'engineresumedata', old_checkpoint['engineresumedata'])
                new_checkpoint.set('state', 'dlstate', old_checkpoint['dlstate'])
                new_checkpoint.set('state', 'metainfo', old_checkpoint['metainfo'])
                with open(old_filename.replace('.pickle', '.state'), "wb") as new_file:
                    new_checkpoint.write(new_file)

                os.remove(old_filename)
