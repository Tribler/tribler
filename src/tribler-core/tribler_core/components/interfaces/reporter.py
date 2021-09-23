from tribler_core.components.base import Component, testcomponent


class ReporterComponent(Component):
    enable_in_gui_test_mode = True

    user_id_str: str


@testcomponent
class ReporterComponentMock(ReporterComponent):
    user_id_str = 'user_id'
