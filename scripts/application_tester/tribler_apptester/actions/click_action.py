from tribler_apptester.action import Action


class ClickAction(Action):
    """
    This action clicks on an object in the GUI.
    """

    def __init__(self, click_obj_name, left_button=True):
        super(ClickAction, self).__init__()
        self.click_obj_name = click_obj_name
        self.left_button = left_button

    def action_code(self):
        button_spec = "LeftButton" if self.left_button else "RightButton"
        return "QTest.mouseClick(%s, Qt.%s)" % (self.click_obj_name, button_spec)

    def required_imports(self):
        return ["from PyQt5.QtTest import QTest", "from PyQt5.QtCore import Qt"]


class ClickSequenceAction(Action):
    """
    This action clicks on multiple object in the GUI.
    """

    def __init__(self, click_obj_names):
        super(ClickSequenceAction, self).__init__()
        self.click_obj_names = click_obj_names

    def action_code(self):
        code = ""
        for click_obj_name in self.click_obj_names:
            code += "QTest.mouseClick(%s, Qt.LeftButton)\n" % click_obj_name
            code += "QTest.qWait(1000)\n"

        return code

    def required_imports(self):
        return ["from PyQt5.QtTest import QTest", "from PyQt5.QtCore import Qt"]


class TableViewClickAction(Action):
    """
    This action clicks on a specific row in a table view.
    """

    def __init__(self, table_view_obj_name, row_index):
        super(TableViewClickAction, self).__init__()
        self.table_view_obj_name = table_view_obj_name
        self.row_index = row_index

    def action_code(self):
        code = """table_view = %s
x = table_view.columnViewportPosition(0)
y = table_view.rowViewportPosition(%d)
index = table_view.indexAt(QPoint(x, y))
table_view.on_table_item_clicked(index)
        """ % (self.table_view_obj_name, self.row_index)

        return code

    def required_imports(self):
        return ["from PyQt5.QtCore import QPoint"]


class RandomTableViewClickAction(Action):
    """
    This action clicks on a random row in a table view.
    """

    def __init__(self, table_view_obj_name):
        super(RandomTableViewClickAction, self).__init__()
        self.table_view_obj_name = table_view_obj_name

    def action_code(self):
        code = """table_view = %s
random_row = randint(0, table_view.model().rowCount() - 1)
x = table_view.columnViewportPosition(0)
y = table_view.rowViewportPosition(random_row)
index = table_view.indexAt(QPoint(x, y))
table_view.on_table_item_clicked(index)
        """ % self.table_view_obj_name

        return code

    def required_imports(self):
        return ["from PyQt5.QtCore import QPoint", "from random import randint"]
