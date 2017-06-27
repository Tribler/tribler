from Tribler.Core.Modules.restapi import get_param
from Tribler.Test.test_as_server import TestAsServer


class TestBaseApi(TestAsServer):
    """
    Test some basic functionality of the restful API
    """

    def test_get_parameters(self):
        """
        Test the get_parameters method
        """
        parameters = {'abc': [3]}
        self.assertIsNone(get_param(parameters, 'abcd'))
        self.assertIsNotNone(get_param(parameters, 'abc'))
