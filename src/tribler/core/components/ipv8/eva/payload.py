from ipv8.messaging.lazy_payload import VariablePayload, vp_compile


@vp_compile
class WriteRequest(VariablePayload):
    format_list = ['I', 'I', 'raw']
    names = ['data_size', 'nonce', 'info']


@vp_compile
class ReadRequest(VariablePayload):
    format_list = ['I', 'raw']
    names = ['nonce', 'info']


@vp_compile
class Acknowledgement(VariablePayload):
    format_list = ['I', 'I', 'I']
    names = ['number', 'window_size', 'nonce']


@vp_compile
class Data(VariablePayload):
    format_list = ['I', 'I', 'raw']
    names = ['number', 'nonce', 'data']


@vp_compile
class Error(VariablePayload):
    format_list = ['?', 'I', 'I', 'raw']
    names = ['incoming', 'code', 'nonce', 'message']
