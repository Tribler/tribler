from typing import Optional

from tribler_common.sentry_reporter.sentry_reporter import SentryReporter


class AddBreadcrumbOnShowMixin:
    """This class has been designed for extending QWidget and QDialog instances
    and send breadcrumbs on a show event.
    """

    def __init__(self):
        self.sentry_reporter: Optional[SentryReporter] = None

    def set_sentry_reporter(self, sentry_reporter: SentryReporter):
        self.sentry_reporter = sentry_reporter

    def showEvent(self, *args):
        super().showEvent(*args)

        self.sentry_reporter.add_breadcrumb(message=f'{self.__class__.__name__}.Show', category='UI', level='info')
