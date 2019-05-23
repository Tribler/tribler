from __future__ import absolute_import

from ipv8.messaging.lazy_payload import VariablePayload


class SearchRequestPayload(VariablePayload):
    format_list = ['I', 'varlenH', 'varlenH', 'varlenH', '?', '?']
    names = ['id', 'query_filter', 'metadata_type', 'sort_by', 'sort_asc', 'hide_xxx']


class SearchResponsePayload(VariablePayload):
    format_list = ['I', 'raw']
    names = ['id', 'raw_blob']
