from time import time


# default packet data size
DEFAULT_BLOCK_SIZE = 512

# default timeout and maximum retries
DEFAULT_TIMEOUT = 3
DEFAULT_MAX_RETRIES = 2


class Session(object):

    def __init__(self, is_client, address, request, file_name, file_data, file_size, extra_info=None,
                 block_size=DEFAULT_BLOCK_SIZE, timeout=DEFAULT_TIMEOUT,
                 success_callback=None, failure_callback=None,
                 max_retries=DEFAULT_MAX_RETRIES):
        self.is_client = is_client
        self.address = address
        self.request = request
        self.file_name = file_name
        self.file_data = file_data
        self.file_size = file_size

        self.extra_info = extra_info

        self.block_number = 0
        self.block_size = block_size
        self.timeout = timeout
        self.success_callback = success_callback
        self.failure_callback = failure_callback

        self.last_read_count = None

        self.last_contact_time = time()
        self.last_received_packet = None
        self.last_sent_packet = None

        # extra information
        self.is_done = False
        self.is_failed = False
        self.max_retries = max_retries
        self.retry_count = 0

        self.next_func = None

    def __str__(self):
        return "TFTP[%s:%s][%s]" % (self.address[0], self.address[1], self.file_name.encode('utf8'))

    def __unicode__(self):
        return u"TFTP[%s:%s][%s]" % (self.address[0], self.address[1], self.file_name)
