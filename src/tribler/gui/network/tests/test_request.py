import random
from typing import Dict
from unittest.mock import MagicMock, Mock, patch

from PyQt5.QtNetwork import QNetworkReply

from tribler.gui.network.request import REQUEST_ID, Request


def test_default_constructor():
    request = Request(
        endpoint='endpoint'
    )
    assert request


def test_dict_data_constructor():
    """ Test that data becomes raw_data as an encoded json
    """
    request = Request(
        endpoint='endpoint',
        data={
            'key': 'value'
        }
    )
    assert request.raw_data == b'{"key": "value"}'


def test_bytes_data_constructor():
    request = Request(
        endpoint='endpoint',
        data=b'bytes'
    )
    assert request.raw_data == b'bytes'


def test_str_data_constructor():
    request = Request(
        endpoint='endpoint',
        data='str'
    )
    assert request.raw_data == b'str'


def test_on_finished():
    # Test that if 'request.reply' is empty, the `on_success` callback is not called
    # see: https://github.com/Tribler/tribler/issues/7333
    on_success = MagicMock()
    request = Request(endpoint='endpoint', on_success=on_success)
    request.manager = MagicMock()
    request.reply = MagicMock(readAll=MagicMock(return_value=b''))

    request.on_finished()

    on_success.assert_not_called()


def test_on_finished_on_success_http_response():
    """
    Test that if HTTP response is available, it is prioritised for processing
    and any QT NetworkReply errors are ignored.
    """
    # pylint: disable=protected-access
    request = Request(endpoint='endpoint')

    request.manager = MagicMock()
    request._handle_http_response = MagicMock()
    request._handle_network_reply_errors = MagicMock()
    request.reply = MagicMock(attribute=MagicMock(return_value=random.randint(100, 600)))  # any valid http status code

    request.on_finished()

    request._handle_http_response.assert_called()
    request._handle_network_reply_errors.assert_not_called()


def test_on_finished_on_network_error():
    """
    Test that if there is no proper HTTP response,
    then QT NetworkReply errors are only handled.
    """
    # pylint: disable=protected-access
    request = Request(endpoint='endpoint')

    request.manager = MagicMock()
    request._handle_http_response = MagicMock()
    request._handle_network_reply_errors = MagicMock()

    qt_network_error_code = 1  # Any non-zero value
    http_status_code = None
    request.reply = MagicMock(error=MagicMock(return_value=qt_network_error_code),
                              attribute=MagicMock(return_value=http_status_code))

    request.on_finished()

    request._handle_http_response.assert_not_called()
    request._handle_network_reply_errors.assert_called()


def test_set_id():
    # Test that the id is set correctly during `on_finished` callback call
    actual_id = None

    def on_success(json: Dict):
        nonlocal actual_id
        actual_id = json[REQUEST_ID]

    request = Request('endpoint', on_success=on_success)
    request.manager = Mock()
    request.reply = Mock(
        error=Mock(return_value=QNetworkReply.NoError),
        readAll=Mock(return_value=b'{"a": "b"}')
    )
    request.id = 10
    request.on_finished()

    assert actual_id == 10
