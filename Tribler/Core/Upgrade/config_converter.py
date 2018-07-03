import ast
import os
from ConfigParser import RawConfigParser, DuplicateSectionError, NoSectionError, MissingSectionHeaderError
import logging
from glob import iglob

from Tribler.Core.simpledefs import STATEDIR_DLPSTATE_DIR

from Tribler.Core.Config.tribler_config import TriblerConfig
from Tribler.Core.exceptions import InvalidConfigException
logger = logging.getLogger(__name__)


def convert_config_to_tribler71(current_config, state_dir=None):
    """
    Convert the Config files libtribler.conf and tribler.conf to the newer triblerd.conf and cleanup the files
    when we are done.

    :param: current_config: the current config in which we merge the old config files.
    :return: the newly edited TriblerConfig object with the old data inserted.
    """
    state_dir = state_dir or TriblerConfig.get_default_state_dir()
    libtribler_file_loc = os.path.join(state_dir, "libtribler.conf")
    if os.path.exists(libtribler_file_loc):
        libtribler_cfg = RawConfigParser()
        libtribler_cfg.read(libtribler_file_loc)
        current_config = add_libtribler_config(current_config, libtribler_cfg)
        os.remove(libtribler_file_loc)

    tribler_file_loc = os.path.join(state_dir, "tribler.conf")
    if os.path.exists(tribler_file_loc):
        tribler_cfg = RawConfigParser()
        tribler_cfg.read(tribler_file_loc)
        current_config = add_tribler_config(current_config, tribler_cfg)
        os.remove(tribler_file_loc)

    # We also have to update all existing downloads, in particular, rename the section 'downloadconfig' to
    # 'download_defaults'.
    for _, filename in enumerate(iglob(
            os.path.join(state_dir, STATEDIR_DLPSTATE_DIR, '*.state'))):
        download_cfg = RawConfigParser()
        try:
            with open(filename) as cfg_file:
                download_cfg.readfp(cfg_file, filename=filename)
        except MissingSectionHeaderError:
            logger.error("Removing download state file %s since it appears to be corrupt", filename)
            os.remove(filename)

        try:
            download_items = download_cfg.items("downloadconfig")
            download_cfg.add_section("download_defaults")
            for download_item in download_items:
                download_cfg.set("download_defaults", download_item[0], download_item[1])
            download_cfg.remove_section("downloadconfig")
            with open(filename, "w") as output_config_file:
                download_cfg.write(output_config_file)
        except (NoSectionError, DuplicateSectionError):
            # This item has already been converted
            pass

    return current_config


def add_tribler_config(new_config, old_config):
    """
    Add the old values of the tribler.conf file to the newer Config file.

    :param new_config: The Config file to which the old data can be written
    :param old_config: A RawConfigParser containing the old tribler.conf Config file
    :return: the edited Config file
    """
    config = new_config.copy()
    for section in old_config.sections():
        for (name, string_value) in old_config.items(section):
            if string_value == "None":
                continue

            # Attempt to interpret string_value as a string, number, tuple, list, dict, boolean or None
            try:
                value = ast.literal_eval(string_value)
            except (ValueError, SyntaxError):
                value = string_value

            temp_config = config.copy()
            if section == "Tribler" and name == "default_anonymity_enabled":
                temp_config.set_default_anonymity_enabled(value)
            if section == "Tribler" and name == "default_number_hops":
                temp_config.set_default_number_hops(value)
            if section == "downloadconfig" and name == "saveas":
                temp_config.config["download_defaults"]["saveas"] = value
            if section == "downloadconfig" and name == "seeding_mode":
                temp_config.config["download_defaults"]["seeding_mode"] = value
            if section == "downloadconfig" and name == "seeding_ratio":
                temp_config.config["download_defaults"]["seeding_ratio"] = value
            if section == "downloadconfig" and name == "seeding_time":
                temp_config.config["download_defaults"]["seeding_time"] = value
            if section == "downloadconfig" and name == "version":
                temp_config.config["download_defaults"]["version"] = value

            try:
                temp_config.validate()
                config = temp_config
            except InvalidConfigException as exc:
                logger.debug("The following field in the old tribler.conf was wrong: %s", exc.args)
    return config


def add_libtribler_config(new_config, old_config):
    """
    Add the old values of the libtribler.conf file to the newer Config file.

    :param new_config: the Config file to which the old data can be written
    :param old_config: a RawConfigParser containing the old libtribler.conf Config file
    :return: the edited Config file
    """
    config = new_config.copy()
    for section in old_config.sections():
        for (name, string_value) in old_config.items(section):
            if string_value == "None":
                continue

            # Attempt to interpret string_value as a string, number, tuple, list, dict, boolean or None
            try:
                value = ast.literal_eval(string_value)
            except (ValueError, SyntaxError):
                value = string_value

            temp_config = config.copy()
            if section == "general" and name == "state_dir":
                temp_config.set_state_dir(value)
            elif section == "general" and name == "eckeypairfilename":
                temp_config.set_permid_keypair_filename(value)
            elif section == "general" and name == "megacache":
                temp_config.set_megacache_enabled(value)
            elif section == "general" and name == "videoanalyserpath":
                temp_config.set_video_analyser_path(value)
            elif section == "general" and name == "log_dir":
                temp_config.set_log_dir(value)
            elif section == "allchannel_community" and name == "enabled":
                temp_config.set_channel_search_enabled(value)
            elif section == "channel_community" and name == "enabled":
                temp_config.set_channel_community_enabled(value)
            elif section == "preview_channel_community" and name == "enabled":
                temp_config.set_preview_channel_community_enabled(value)
            elif section == "search_community" and name == "enabled":
                temp_config.set_torrent_search_enabled(value)
            elif section == "tunnel_community" and name == "enabled":
                temp_config.set_tunnel_community_enabled(value)
            elif section == "tunnel_community" and name == "socks5_listen_ports":
                if isinstance(value, list):
                    temp_config.set_tunnel_community_socks5_listen_ports(value)
            elif section == "tunnel_community" and name == "exitnode_enabled":
                temp_config.set_tunnel_community_exitnode_enabled(value)
            elif section == "general" and name == "ec_keypair_filename_multichain":
                temp_config.set_trustchain_permid_keypair_filename(value)
            elif section == "metadata" and name == "enabled":
                temp_config.set_metadata_enabled(value)
            elif section == "metadata" and name == "store_dir":
                temp_config.set_metadata_store_dir(value)
            elif section == "mainline_dht" and name == "enabled":
                temp_config.set_mainline_dht_enabled(value)
            elif section == "mainline_dht" and name == "mainline_dht_port":
                temp_config.set_mainline_dht_port(value)
            elif section == "torrent_checking" and name == "enabled":
                temp_config.set_torrent_checking_enabled(value)
            elif section == "torrent_store" and name == "enabled":
                temp_config.set_torrent_store_enabled(value)
            elif section == "torrent_store" and name == "dir":
                temp_config.set_torrent_store_dir(value)
            elif section == "torrent_collecting" and name == "enabled":
                temp_config.set_torrent_collecting_enabled(value)
            elif section == "torrent_collecting" and name == "torrent_collecting_max_torrents":
                temp_config.set_torrent_collecting_max_torrents(value)
            elif section == "torrent_collecting" and name == "torrent_collecting_dir":
                temp_config.set_torrent_collecting_dir(value)
            elif section == "libtorrent" and name == "lt_proxytype":
                temp_config.config["libtorrent"]["proxy_type"] = value
            elif section == "libtorrent" and name == "lt_proxyserver":
                temp_config.config["libtorrent"]["proxy_server"] = value
            elif section == "libtorrent" and name == "lt_proxyauth":
                temp_config.config["libtorrent"]["proxy_auth"] = value
            elif section == "libtorrent" and name == "max_connections_download":
                temp_config.set_libtorrent_max_conn_download(value)
            elif section == "libtorrent" and name == "max_download_rate":
                temp_config.set_libtorrent_max_download_rate(value)
            elif section == "libtorrent" and name == "max_upload_rate":
                temp_config.set_libtorrent_max_upload_rate(value)
            elif section == "libtorrent" and name == "utp":
                temp_config.set_libtorrent_utp(value)
            elif section == "libtorrent" and name == "anon_listen_port":
                temp_config.set_anon_listen_port(value)
            elif section == "libtorrent" and name == "anon_proxytype":
                temp_config.config["libtorrent"]["anon_proxy_type"] = value
            elif section == "libtorrent" and name == "anon_proxyserver":
                if isinstance(value, tuple) and isinstance(value[1], list):
                    temp_config.config["libtorrent"]["anon_proxy_server_ip"] = value[0]
                    temp_config.config["libtorrent"]["anon_proxy_server_ports"] = [str(port) for port in value[1]]
            elif section == "libtorrent" and name == "anon_proxyauth":
                temp_config.config["libtorrent"]["anon_proxy_auth"] = value
            elif section == "dispersy" and name == "enabled":
                temp_config.set_dispersy_enabled(value)
            elif section == "dispersy" and name == "dispersy_port":
                temp_config.set_dispersy_port(value)
            elif section == "video" and name == "enabled":
                temp_config.set_video_server_enabled(value)
            elif section == "video" and name == "port":
                temp_config.set_video_server_port(value)
            elif section == "watch_folder" and name == "enabled":
                temp_config.set_watch_folder_enabled(value)
            elif section == "watch_folder" and name == "watch_folder_dir":
                temp_config.set_watch_folder_path(value)
            elif section == "http_api" and name == "enabled":
                temp_config.set_http_api_enabled(value)
            elif section == "http_api" and name == "port":
                temp_config.set_http_api_port(value)
            elif section == "credit_mining" and name == "enabled":
                temp_config.set_credit_mining_enabled(value)
            elif section == "credit_mining" and name == "sources":
                temp_config.set_credit_mining_sources(value)

            try:
                temp_config.validate()
                config = temp_config
            except InvalidConfigException as exc:
                logger.debug("The following field in the old libtribler.conf was wrong: %s", exc.args)

    return config
