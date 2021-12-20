from io import BytesIO, TextIOWrapper
from unittest.mock import MagicMock, call

from tribler_common.logger.streams import StreamWrapper


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
    stream.write.side_effect = [UnicodeEncodeError('ascii','zzz', 0, 1, 'error message'), None]
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
