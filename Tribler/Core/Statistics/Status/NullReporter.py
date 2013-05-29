import Status


class NullReporter(Status.PeriodicStatusReporter):

    """
    This reporter flushes all events down the drain periodically,
    ensuring that there is no retained memory.
    """

    def add_element(self, element):
        self.report()

    def report(self):
        """
        Create the report in XML and send it
        """
        self.get_events()
