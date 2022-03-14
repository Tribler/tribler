from tribler.gui import gui_sentry_reporter


class AddBreadcrumbOnShowMixin:
    """This class has been designed for extending QWidget and QDialog instances
    and send breadcrumbs on a show event.
    """

    def showEvent(self, *args):
        super().showEvent(*args)

        gui_sentry_reporter.add_breadcrumb(message=f'{self.__class__.__name__}.Show', category='UI', level='info')
