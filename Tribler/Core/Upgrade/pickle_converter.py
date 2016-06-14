import io
import os
import glob
import json
import pickle
import cPickle
import StringIO

from ConfigParser import RawConfigParser

from Tribler.Core.SessionConfig import SessionStartupConfig, SessionConfigInterface
from Tribler.Core.DownloadConfig import DefaultDownloadStartupConfig, get_default_dscfg_filename
from Tribler.Core.simpledefs import PERSISTENTSTATE_CURRENTVERSION, STATEDIR_GUICONFIG


class PickleConverter(object):
    """
    This class is responsible for converting old .pickle files used for configuration files to a newer .state format.
    """

    def __init__(self, session):
        self.session = session

    def convert(self):
        """
        Calling this method will convert all configuration files to the newer .state format.
        """
        self.convert_session_config()
        self.convert_main_config()
        self.convert_default_download_config()
        self.convert_download_checkpoints()

    def convert_session_config(self):
        """
        Convert the sessionconfig.pickle file to libtribler.conf. Do nothing if we do not have a pickle file.
        """
        old_filename = os.path.join(self.session.get_state_dir(), 'sessconfig.pickle')
        new_filename = SessionConfigInterface.get_default_config_filename(self.session.get_state_dir())

        if not os.path.exists(old_filename):
            return

        with open(old_filename, "rb") as old_file:
            sessconfig = pickle.load(old_file)

        # Upgrade to new config
        sconfig = SessionStartupConfig()
        for key, value in sessconfig.iteritems():
            if key in ['state_dir', 'install_dir', 'ip', 'minport', 'maxport', 'bind', 'ipv6_enabled',
                       'ipv6_binds_v4', 'timeout', 'timeout_check_interval', 'eckeypairfilename', 'megacache',
                       'nickname', 'mugshot', 'videoanalyserpath', 'peer_icon_path', 'live_aux_seeders']:
                sconfig.sessconfig.set('general', key, value)
            if key in ['mainline_dht', 'mainline_dht_port']:
                sconfig.sessconfig.set('mainline_dht', 'enabled' if key == 'mainline_dht' else key, value)
            if key == 'torrent_checking':
                sconfig.sessconfig.set('torrent_checking', 'enabled', value)
            if key in ['torrent_collecting', 'dht_torrent_collecting', 'torrent_collecting_max_torrents',
                       'torrent_collecting_dir', 'stop_collecting_threshold']:
                sconfig.sessconfig.set('torrent_collecting', 'enabled' if key == 'torrent_collecting' else key, value)
            if key in ['libtorrent', 'lt_proxytype', 'lt_proxyserver', 'lt_proxyauth']:
                sconfig.sessconfig.set('libtorrent', 'enabled' if key == 'libtorrent' else key, value)
            if key in ['dispersy_port', 'dispersy']:
                sconfig.sessconfig.set('dispersy', 'enabled' if key == 'dispersy' else key, value)

        # Save the new file, remove the old one
        sconfig.save(new_filename)
        os.remove(old_filename)

    def convert_main_config(self):
        """
        Convert the abc.conf, user_download_choice.pickle, gui_settings and recent download history files
        to tribler.conf.
        """
        state_dir = self.session.get_state_dir()
        old_filename = os.path.join(state_dir, 'abc.conf')
        new_filename = os.path.join(state_dir, STATEDIR_GUICONFIG)

        if not os.path.exists(old_filename):
            return

        with io.open(old_filename, 'r', encoding='utf_8_sig') as old_file:
            corrected_config = StringIO.StringIO(old_file.read().replace('[ABC]', '[Tribler]'))

        config = RawConfigParser()
        config.readfp(corrected_config)

        # Convert user_download_choice.pickle
        udcfilename = os.path.join(state_dir, 'user_download_choice.pickle')
        if os.path.exists(udcfilename):
            with open(udcfilename, "r") as udc_file:
                choices = cPickle.Unpickler(udc_file).load()
                choices = dict([(k.encode('hex'), v) for k, v in choices["download_state"].iteritems()])
                config.set('Tribler', 'user_download_choice', json.dumps(choices))
            os.remove(udcfilename)

        # Convert gui_settings
        guifilename = os.path.join(state_dir, 'gui_settings')
        if os.path.exists(guifilename):
            with open(guifilename, "r") as guisettings_file:
                for line in guisettings_file.readlines():
                    key, value = line.split('=')
                    config.set('Tribler', key, value.strip())
            os.remove(guifilename)

        # Convert recent_download_history
        histfilename = os.path.join(state_dir, 'recent_download_history')
        if os.path.exists(histfilename):
            with open(histfilename, "r") as history_file:
                history = []
                for line in history_file.readlines():
                    key, value = line.split('=')
                    if value != '' and value != '\n':
                        history.append(value.replace('\\\\', '\\').strip())
                config.set('Tribler', 'recent_download_history', json.dumps(history))
            os.remove(histfilename)

        with open(new_filename, "wb") as new_file:
            config.write(new_file)
        os.remove(old_filename)

    def convert_default_download_config(self):
        """
        Convert the dlconfig.pickle file to a .state file.
        """
        state_dir = self.session.get_state_dir()
        old_filename = os.path.join(state_dir, 'dlconfig.pickle')
        new_filename = get_default_dscfg_filename(state_dir)

        if not os.path.exists(old_filename):
            return

        with open(old_filename, "rb") as old_file:
            dlconfig = pickle.load(old_file)

        # Upgrade to new config
        ddsconfig = DefaultDownloadStartupConfig.getInstance()
        for key, value in dlconfig.iteritems():
            if key in ['saveas', 'max_upload_rate', 'max_download_rate', 'super_seeder', 'mode', 'selected_files',
                       'correctedfilename']:
                ddsconfig.dlconfig.set('downloadconfig', key, value)

        # Save the new file, remove the old one
        ddsconfig.save(new_filename)
        os.remove(old_filename)
        return ddsconfig

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
                old_checkpoint = None
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
