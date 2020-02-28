# -*- coding:utf-8 -*-
from tribler_core.restapi.util import fix_unicode_array, fix_unicode_dict, get_parameter
from tribler_core.tests.tools.base_test import MockObject, TriblerCoreTest


class TestRestApiUtil(TriblerCoreTest):
    """
    This class contains various tests for the rest api utility methods.
    """

    def test_get_parameter(self):
        """
        Testing the get_parameters method in REST API util class
        """
        self.assertEqual(42, get_parameter({'test': [42]}, 'test'))
        self.assertEqual(None, get_parameter({}, 'test'))

    def test_fix_unicode_array(self):
        """
        Testing the fix of a unicode array
        """
        arr1 = ['a', 'b', 'c', u'd']
        self.assertListEqual(fix_unicode_array(arr1), ['a', 'b', 'c', 'd'])
        arr2 = ['a', b'\xa1']
        self.assertListEqual(fix_unicode_array(arr2), ['a', ''])
        arr3 = [1, 2, 3, '4']
        self.assertListEqual(fix_unicode_array(arr3), [1, 2, 3, '4'])
        arr4 = [{'a': 'b'}]
        self.assertListEqual(fix_unicode_array(arr4), [{'a': 'b'}])

    def test_fix_unicode_dict(self):
        """
        Testing the fix of a unicode dictionary
        """
        dict1 = {'a': 'b', 'c': 'd'}
        self.assertDictEqual(fix_unicode_dict(dict1), {'a': 'b', 'c': 'd'})
        dict2 = {'a': b'\xa2'}
        self.assertDictEqual(fix_unicode_dict(dict2), {'a': ''})
        dict3 = {'a': [1, 2], 'b': ['1', '2']}
        self.assertDictEqual(fix_unicode_dict(dict3), {'a': [1, 2], 'b': ['1', '2']})
        dict4 = {'a': ['1', b'2\xa3']}
        self.assertDictEqual(fix_unicode_dict(dict4), {'a': ['1', '2']})
        dict5 = {'a': ('1', b'2\xa3')}
        self.assertDictEqual(fix_unicode_dict(dict5), {'a': ['1', '2']})
        dict6 = {'a': {'b': b'c\xa4'}}
        self.assertDictEqual(fix_unicode_dict(dict6), {'a': {'b': 'c'}})
        dict7 = {'a': 'ѡ'}
        self.assertDictEqual(fix_unicode_dict(dict7), {'a': u'ѡ'})
        obj = MockObject
        dict8 = {'a': {'b': obj}}
        self.assertDictEqual(fix_unicode_dict(dict8), {'a': {'b': obj}})
