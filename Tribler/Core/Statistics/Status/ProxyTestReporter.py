from LivingLabReporter import LivingLabPeriodicReporter

class ProxyTestPeriodicReporter(LivingLabPeriodicReporter):
    host = "proxytestreporter.tribler.org"
    path = "/post/"
