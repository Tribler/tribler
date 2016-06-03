# Written by Egbert Bouman

#
# Things to handle backward compatability for old-style config files
#

import io
import os
import glob
import json
import pickle
import cPickle
import StringIO

from ConfigParser import RawConfigParser

from Tribler.Core.SessionConfig import SessionStartupConfig
from Tribler.Core.DownloadConfig import DefaultDownloadStartupConfig
from Tribler.Core.simpledefs import PERSISTENTSTATE_CURRENTVERSION


def convertSessionConfig(oldfilename, newfilename):
    # Convert tribler <= 6.2 session config file to tribler 6.3

    # We assume oldfilename exists
    with open(oldfilename, "rb") as f:
        sessconfig = pickle.load(f)

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
    sconfig.save(newfilename)
    os.remove(oldfilename)
    return sconfig


def convertMainConfig(state_dir, oldfilename, newfilename):
    # Convert tribler <= 6.2 config files to tribler 6.3

    # We assume oldfilename exists
    with io.open(oldfilename, 'r', encoding='utf_8_sig') as f:
        corrected_config = StringIO.StringIO(f.read().replace('[ABC]', '[Tribler]'))

    config = RawConfigParser()
    config.readfp(corrected_config)

    # Convert user_download_choice.pickle
    udcfilename = os.path.join(state_dir, 'user_download_choice.pickle')
    if os.path.exists(udcfilename):
        with open(udcfilename, "r") as f:
            choices = cPickle.Unpickler(f).load()
            choices = dict([(k.encode('hex'), v) for k, v in choices["download_state"].iteritems()])
            config.set('Tribler', 'user_download_choice', json.dumps(choices))
        os.remove(udcfilename)

    # Convert gui_settings
    guifilename = os.path.join(state_dir, 'gui_settings')
    if os.path.exists(guifilename):
        with open(guifilename, "r") as f:
            for line in f.readlines():
                key, value = line.split('=')
                config.set('Tribler', key, value.strip())
        os.remove(guifilename)

    # Convert recent_download_history
    histfilename = os.path.join(state_dir, 'recent_download_history')
    if os.path.exists(histfilename):
        with open(histfilename, "r") as f:
            history = []
            for line in f.readlines():
                key, value = line.split('=')
                if value != '' and value != '\n':
                    history.append(value.replace('\\\\', '\\').strip())
            config.set('Tribler', 'recent_download_history', json.dumps(history))
        os.remove(histfilename)

    with open(newfilename, "wb") as f:
        config.write(f)
    os.remove(oldfilename)


def convertDefaultDownloadConfig(oldfilename, newfilename):
    # Convert tribler <= 6.2 default download config file to tribler 6.3

    # We assume oldfilename exists
    with open(oldfilename, "rb") as f:
        dlconfig = pickle.load(f)

    # Upgrade to new config
    ddsconfig = DefaultDownloadStartupConfig()
    for key, value in dlconfig.iteritems():
        if key in ['saveas', 'max_upload_rate', 'max_download_rate', 'super_seeder', 'mode', 'selected_files',
                   'correctedfilename']:
            ddsconfig.dlconfig.set('downloadconfig', key, value)

    # Save the new file, remove the old one
    ddsconfig.save(newfilename)
    os.remove(oldfilename)
    return ddsconfig


def convertDownloadCheckpoints(checkpoint_dir):
    # Convert tribler <= 6.2 download checkpoints to tribler 6.3

    if os.path.exists(checkpoint_dir):
        for old_filename in glob.glob(os.path.join(checkpoint_dir, '*.pickle')):
            old_checkpoint = None
            try:
                with open(old_filename, "rb") as old_file:
                    old_checkpoint = pickle.load(old_file)
            except:
                pass

            if old_checkpoint:
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
