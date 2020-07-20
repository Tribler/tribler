from pathlib import Path

from configobj import ConfigObjError

import pytest

from tribler_core.modules.libtorrent.download_config import DownloadConfig, get_default_dest_dir
from tribler_core.tests.tools.common import TESTS_DATA_DIR


CONFIG_FILES_DIR = TESTS_DATA_DIR / "config_files"


def test_downloadconfig(download_config, tmpdir):
    assert isinstance(download_config.get_dest_dir(), Path)
    download_config.set_dest_dir(tmpdir)
    assert download_config.get_dest_dir() == tmpdir

    download_config.set_hops(4)
    assert download_config.get_hops() == 4

    download_config.set_safe_seeding(False)
    assert not download_config.get_safe_seeding()

    download_config.set_selected_files([1])
    assert download_config.get_selected_files() == [1]

    download_config.set_channel_download(True)
    assert download_config.get_channel_download()

    download_config.set_add_to_channel(True)
    assert download_config.get_add_to_channel()

    download_config.set_bootstrap_download(True)
    assert download_config.get_bootstrap_download()


def test_downloadconfig_copy(download_config):
    dlcfg_copy = download_config.copy()

    assert dlcfg_copy.get_hops() == 0
    assert dlcfg_copy.state_dir == download_config.state_dir


def test_download_save_load(download_config, tmpdir):
    file_path = tmpdir / "downloadconfig.conf"
    download_config.write(file_path)
    assert download_config.load(file_path)


def test_download_load_corrupt(download_config):
    with pytest.raises(ConfigObjError):
        download_config.load(CONFIG_FILES_DIR / "corrupt_download_config.conf")


def test_get_default_dest_dir():
    assert isinstance(get_default_dest_dir(), Path)


def test_default_download_config_load(tmpdir):
    with open(tmpdir / "dlconfig.conf", 'wb') as conf_file:
        conf_file.write(b"[Tribler]\nabc=def")

    dcfg = DownloadConfig.load(tmpdir / "dlconfig.conf")
    assert dcfg.config['Tribler']['abc'] == 'def'


def test_user_stopped(download_config):
    download_config.set_user_stopped(False)
    assert not download_config.get_user_stopped()

    download_config.set_user_stopped(True)
    assert download_config.get_user_stopped()
