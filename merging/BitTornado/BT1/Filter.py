class Filter:
    def __init__(self, callback):
        self.callback = callback

    def check(self, ip, paramslist, headers):

        def params(key, default = None, l = paramslist):
            if l.has_key(key):
                return l[key][0]
            return default

        return None
