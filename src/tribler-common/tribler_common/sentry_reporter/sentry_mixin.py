from tribler_common.sentry_reporter.sentry_reporter import SentryReporter


class AddBreadcrumbOnShowMixin:
    """This class has been designed for extending QWidget and QDialog instances
    and send breadcrumbs on a show event.
    """

    def showEvent(self, *args):
        super().showEvent(*args)

        SentryReporter.add_breadcrumb(message=f'{self.__class__.__name__}.Show', category='UI', level='info')
