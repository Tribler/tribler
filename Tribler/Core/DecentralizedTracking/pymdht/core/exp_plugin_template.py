

class ExperimentalManager:

    def __init__(self, my_id, msg_f):
        pass

    def on_query_received(self, msg):
        pass

    def on_response_received(self, msg, related_query):
        pass

    def on_error_received(self, msg, related_query):
        pass

    def on_timeout(self, related_query):
        pass

    def on_stop(self):
        pass



class ExpObj:
    def __init__(self, value):
        pass
