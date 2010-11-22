from LivingLabReporter import LivingLabPeriodicReporter

class ProxyTestPeriodicReporter(LivingLabPeriodicReporter):
    host = "proxytestreporter.tribler.org"
    path = "/post.py"

#if __name__ == "__main__":
#    from Tribler.Core.Statistics.Status.Status import get_status_holder

#    status = get_status_holder("ProxyTest")
#    status.add_reporter(ProxyTestPeriodicReporter("Test", 5, "test-id"))
#    status.create_and_add_event("foo", ["foo", "bar"])
#    status.create_and_add_event("animals", ["bunnies", "kitties", "doggies"])
#    status.create_and_add_event("numbers", range(255))

#    import time
#    time.sleep(15)
