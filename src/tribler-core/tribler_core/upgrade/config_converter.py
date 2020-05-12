import ast
import base64
import logging
import os
from configparser import MissingSectionHeaderError
from lib2to3.pgen2.parse import ParseError

from configobj import ConfigObj

import libtorrent as lt

from tribler_common.simpledefs import STATEDIR_CHECKPOINT_DIR

from tribler_core.modules.libtorrent.download_config import DownloadConfig
from tribler_core.modules.libtorrent.torrentdef import TorrentDef
from tribler_core.utilities.configparser import CallbackConfigParser
from tribler_core.utilities.unicode import recursive_ungarble_metainfo

logger = logging.getLogger(__name__)


def convert_config_to_tribler74(state_dir):
    """
    Convert the download config files to Tribler 7.4 format. The extensions will also be renamed from .state to .conf
    """
    from lib2to3.refactor import RefactoringTool, get_fixers_from_package
    refactoring_tool = RefactoringTool(fixer_names=get_fixers_from_package('lib2to3.fixes'))

    for filename in (state_dir / STATEDIR_CHECKPOINT_DIR).glob('*.state'):
        convert_state_file_to_conf_74(filename, refactoring_tool=refactoring_tool)


def convert_state_file_to_conf_74(filename, refactoring_tool=None):
    """
    Converts .pstate file (pre-7.4.0) to .conf file.
    :param filename: .pstate file
    :param refactoring_tool: RefactoringTool instance if using Python3
    :return: None
    """
    def _fix_state_config(config):
        for section, option in [('state', 'metainfo'), ('state', 'engineresumedata')]:
            value = config.get(section, option, literal_eval=False)
            try:
                value = str(refactoring_tool.refactor_string(value + '\n', option + '_2to3'))
                ungarbled_dict = recursive_ungarble_metainfo(ast.literal_eval(value))
                value = ungarbled_dict or ast.literal_eval(value)
                config.set(section, option, base64.b64encode(lt.bencode(value)).decode('utf-8'))
            except (ValueError, SyntaxError, ParseError) as ex:
                logger.error("Config could not be fixed, probably corrupted. Exception: %s %s", type(ex), str(ex))
                return None
        return config

    old_config = CallbackConfigParser()
    try:
        old_config.read_file(str(filename))
    except MissingSectionHeaderError:
        logger.error("Removing download state file %s since it appears to be corrupt", filename)
        os.remove(filename)

    # We first need to fix the .state file such that it has the correct metainfo/resumedata.
    # If the config cannot be fixed, it is likely corrupted in which case we simply remove the file.
    fixed_config = _fix_state_config(old_config)
    if not fixed_config:
        logger.error("Removing download state file %s since it could not be fixed", filename)
        os.remove(filename)
        return

    # Remove dlstate since the same information is already stored in the resumedata
    if old_config.has_option('state', 'dlstate'):
        old_config.remove_option('state', 'dlstate')

        new_config = ConfigObj(infile=str(filename)[:-6] + '.conf', encoding='utf8')
        for section in old_config.sections():
            for key, _ in old_config.items(section):
                val = old_config.get(section, key)
                if section not in new_config:
                    new_config[section] = {}
                new_config[section][key] = val
        new_config.write()
        os.remove(filename)


def convert_config_to_tribler75(state_dir):
    """
    Convert the download config files from Tribler 7.4 to 7.5 format.
    """
    for filename in (state_dir / STATEDIR_CHECKPOINT_DIR).glob('*.conf'):
        config = DownloadConfig.load(filename)

        # Convert resume data
        resumedata = config.get_engineresumedata()
        if b'mapped_files' in resumedata:
            resumedata.pop(b'mapped_files')
            config.set_engineresumedata(resumedata)
            config.write(str(filename))

        # Convert metainfo
        metainfo = config.get_metainfo()
        if not config.config['download_defaults'].get('selected_files') or not metainfo:
            continue  # no conversion needed/possible, selected files will be reset to their default (i.e., all files)
        tdef = TorrentDef.load_from_dict(metainfo)
        config.set_selected_files([tdef.get_index_of_file_in_files(fn)
                                   for fn in config.config['download_defaults'].pop('selected_files')])
        config.write(str(filename))
