from time import time


# default packet data size
DEFAULT_BLOCK_SIZE = 512

# default timeout and maximum retries
DEFAULT_TIMEOUT = 2


class Session(object):

    def __init__(self, is_client, session_id, address, request, file_name, file_data, file_size, checksum,
                 extra_info=None, block_size=DEFAULT_BLOCK_SIZE, timeout=DEFAULT_TIMEOUT,
                 success_callback=None, failure_callback=None):
        self.is_client = is_client
        self.session_id = session_id
        self.address = address
        self.request = request
        self.file_name = file_name
        self.file_data = file_data
        self.file_size = file_size
        self.checksum = checksum

        self.extra_info = extra_info

        self.block_number = 0
        self.block_size = block_size
        self.timeout = timeout
        self.success_callback = success_callback
        self.failure_callback = failure_callback

        self.last_contact_time = time()
        self.last_received_packet = None
        self.last_sent_packet = None
        self.is_waiting_for_last_ack = False

        self.retries = 0

        self.is_done = False
        self.is_failed = False

        self.next_func = None

    def __str__(self):
        type_str = "C" if self.is_client else "S"
        return "TFTP[%s %s %s:%s][%s]" % (self.session_id, type_str, self.address[0], self.address[1],
                                          self.file_name.encode('utf8'))

    def __unicode__(self):
        type_str = u"C" if self.is_client else u"S"
        return u"TFTP[%s %s %s:%s][%s]" % (self.session_id, type_str, self.address[0], self.address[1], self.file_name)
