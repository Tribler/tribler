from tribler_apptester.action import Action


class TableViewSelectAction(Action):
    """
    This action selects a specific row in a table view.
    """

    def __init__(self, table_view_obj_name, row_index):
        super(TableViewSelectAction, self).__init__()
        self.table_view_obj_name = table_view_obj_name
        self.row_index = row_index

    def action_code(self):
        code = """table_view = %s
x = table_view.columnViewportPosition(0)
y = table_view.rowViewportPosition(%d)
index = table_view.indexAt(QPoint(x, y))
table_view.setCurrentIndex(index)
        """ % (self.table_view_obj_name, self.row_index)

        return code

    def required_imports(self):
        return ["from PyQt5.QtCore import QPoint"]


class TableViewRandomSelectAction(Action):
    """
    This action selects a random row in a table view.
    """

    def __init__(self, table_view_obj_name):
        super(TableViewRandomSelectAction, self).__init__()
        self.table_view_obj_name = table_view_obj_name

    def action_code(self):
        code = """table_view = %s
random_row = randint(0, table_view.model().rowCount() - 1)
x = table_view.columnViewportPosition(0)
y = table_view.rowViewportPosition(random_row)
index = table_view.indexAt(QPoint(x, y))
table_view.setCurrentIndex(index)
        """ % self.table_view_obj_name

        return code

    def required_imports(self):
        return ["from random import randint", "from PyQt5.QtCore import QPoint"]
