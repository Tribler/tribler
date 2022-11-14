from io import BytesIO, TextIOWrapper
from unittest.mock import MagicMock, Mock, call, patch

from tribler.core.logger.logger import get_logger_config_path, setup_logging
from tribler.core.logger.logger_streams import StreamWrapper
from tribler.core.utilities.path_util import Path


@patch('tribler.core.logger.logger.__file__', '/a/b/c/logger.py')
def test_get_logger_config_path():
    config_path = get_logger_config_path()
    # take the last part of the path to ignore a drive name on Windows
    assert config_path.parts[-4:] == ('a', 'b', 'c', 'logger.yaml')

    with patch('sys._MEIPASS', '/x/y/z/', create=True):
        config_path = get_logger_config_path()
        assert config_path == Path('/x/y/z/tribler_source/tribler/core/logger/logger.yaml')


@patch('logging.basicConfig')
def test_setup_logging_no_config(mocked_basic_config: Mock, tmp_path: Path):
    """Test that in the case of a missed config, the `basicConfig` function is called.
    """
    config_path = tmp_path / 'non_existent.conf'
    assert not config_path.exists()

    setup_logging('', Path(''), config_path)
    assert mocked_basic_config.called


@patch('yaml.safe_load')
@patch('logging.config.dictConfig')
@patch('tribler.core.logger.logger.logger')
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
    logger.info.assert_has_calls(
        [
            call('Load logger config: app_mode=<app-mode>, config_path=<config-path>, dir=<log-dir>'),
            call("Config loaded for app_mode=<app-mode>"),
        ]
    )


@patch('logging.basicConfig')
def test_setup_logging_exception(mocked_basic_config: Mock, tmp_path: Path):
    """Test that in the case of an exception in the `setup_logging` function,
    the `basicConfig` function is called.
    """
    log_dir = tmp_path
    config_path = tmp_path / 'config.conf'
    config_path.write_text('wrong config content')
    setup_logging('', log_dir, config_path)

    assert mocked_basic_config.called


def test_stream_wrapper_write_ascii():
    stream = MagicMock()
    wrapper = StreamWrapper(stream)
    wrapper.write('hello')
    stream.write.assert_called_once_with('hello')

    byte_stream = BytesIO()
    stream = TextIOWrapper(byte_stream, encoding='ascii')
    wrapper = StreamWrapper(stream)
    wrapper.write("hello")
    wrapper.flush()
    assert byte_stream.getvalue() == b"hello"


def test_stream_wrapper_write_non_ascii_without_exception():
    stream = MagicMock()
    wrapper = StreamWrapper(stream)
    wrapper.write('hello привет')
    stream.write.assert_called_once_with('hello привет')

    byte_stream = BytesIO()
    stream = TextIOWrapper(byte_stream, encoding='cp1251')
    wrapper = StreamWrapper(stream)
    wrapper.write("hello привет")
    wrapper.flush()
    assert byte_stream.getvalue() == 'hello привет'.encode('cp1251')


def test_stream_wrapper_write_non_ascii_with_exception():
    stream = MagicMock(encoding='ascii')
    stream.write.side_effect = [UnicodeEncodeError('ascii', 'zzz', 0, 1, 'error message'), None]
    wrapper = StreamWrapper(stream)
    wrapper.write('hello привет')
    stream.write.assert_has_calls([call('hello привет'), call('hello \\u043f\\u0440\\u0438\\u0432\\u0435\\u0442')])

    byte_stream = BytesIO()
    stream = TextIOWrapper(byte_stream, encoding='ascii')
    wrapper = StreamWrapper(stream)
    wrapper.write("hello привет")
    wrapper.flush()
    assert byte_stream.getvalue() == b'hello \\u043f\\u0440\\u0438\\u0432\\u0435\\u0442'


def test_stream_flush_and_close():
    stream = MagicMock()
    wrapper = StreamWrapper(stream)
    wrapper.write('hello')

    stream.flush.assert_not_called()
    wrapper.flush()
    stream.flush.assert_called_once()

    stream.close.assert_not_called()
    wrapper.close()
    stream.close.assert_called_once()
