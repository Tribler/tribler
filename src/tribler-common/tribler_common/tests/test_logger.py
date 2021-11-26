import logging
from unittest.mock import MagicMock, Mock, call, patch

from tribler_common.logger import get_logger_config_path, setup_logging


@patch('tribler_common.logger.__file__', '/a/b/c/logger.py')
def test_get_logger_config_path():
    config_path = get_logger_config_path()
    # take the last part of the path to ignore a drive name on Windows
    assert config_path.parts[-4:] == ('a', 'b', 'c', 'logger.yaml')

    with patch('sys._MEIPASS', '/x/y/z/', create=True):
        config_path = get_logger_config_path()
        assert config_path.parts[-6:] == ('x', 'y', 'z', 'tribler_source', 'tribler_common', 'logger.yaml')


@patch('tribler_common.logger.logger')
@patch('sys.stdout')
@patch('sys.stderr')
@patch('builtins.print')
@patch('logging.basicConfig')
def test_setup_logging_no_config(basic_config: Mock, print_: Mock, stderr: Mock, stdout: Mock, logger: Mock):
    config_path = MagicMock()
    config_path.exists.return_value = False
    config_path.__str__.return_value = '<config-path>'

    setup_logging('<app-mode>', '<log-dir>', config_path)

    logger.info.assert_called_once_with("Load logger config: app_mode=<app-mode>, "
                                        "config_path=<config-path>, dir=<log-dir>")
    print_.assert_called_once_with("Logger config not found in <config-path>. Using default configs.", file=stderr)
    basic_config.assert_called_once_with(level=logging.INFO, stream=stdout)


@patch('yaml.safe_load')
@patch('logging.config.dictConfig')
@patch('tribler_common.logger.logger')
def test_setup_logging(logger: Mock, dict_config: Mock, yaml_safe_load: Mock):
    log_dir = MagicMock()
    log_dir.__str__.return_value = '<log-dir>'
    log_dir.exists.return_value = False

    config_path = MagicMock()
    config_path.__str__.return_value = '<config-path>'
    config_path.exists.return_value = True
    config_path.open().__enter__().read().replace().replace.return_value = '<config-text>'

    yaml_safe_load.return_value = '<config>'

    setup_logging('<app-mode>', log_dir, config_path)

    log_dir.mkdir.assert_called_once_with(parents=True)

    yaml_safe_load.assert_called_once_with('<config-text>')
    dict_config.assert_called_once_with('<config>')
    assert logger.info.call_count == 2
    logger.info.assert_has_calls([
        call('Load logger config: app_mode=<app-mode>, config_path=<config-path>, dir=<log-dir>'),
        call("Config loaded for app_mode=<app-mode>")
    ])

@patch('tribler_common.logger.logger')
@patch('sys.stdout')
@patch('sys.stderr')
@patch('builtins.print')
@patch('logging.basicConfig')
def test_setup_logging_exception(basic_config: Mock, print_: Mock, stderr: Mock, stdout: Mock, logger: Mock):
    error = ZeroDivisionError()

    log_dir = MagicMock()
    log_dir.__str__.return_value = '<log-dir>'
    log_dir.exists.return_value = True
    log_dir.joinpath.side_effect = error

    config_path = MagicMock()
    config_path.__str__.return_value = '<config-path>'
    config_path.exists.return_value = True

    setup_logging('<app-mode>', log_dir, config_path)

    logger.info.assert_called_once_with("Load logger config: app_mode=<app-mode>, "
                                        "config_path=<config-path>, dir=<log-dir>")
    print_.assert_called_once_with('Error in loading logger config. Using default configs. Error:', error, file=stderr)
    basic_config.assert_called_once_with(level=logging.INFO, stream=stdout)
