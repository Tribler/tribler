from tribler_apptester.action import Action


class TestExceptionAction(Action):
    """
    This action deliberately makes an exception to test that Sentry correctly receives this error
    """

    def action_code(self):
        return """
class TestTriblerExceptionFromAppTester(Exception):
    pass
raise TestTriblerExceptionFromAppTester('Test Tribler exception induced by Application Tester')
"""
