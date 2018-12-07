"""
Category.

Author(s):  Yuan Yuan, Jelle Roozenburg
"""
from __future__ import absolute_import, division
from functools import cmp_to_key
import logging
import os
import re
from six.moves.configparser import MissingSectionHeaderError, ParsingError

from Tribler.Core.Category.FamilyFilter import XXXFilter
from Tribler.Core.Category.init_category import getCategoryInfo
from Tribler.Core.Utilities.install_dir import get_lib_path

CATEGORY_CONFIG_FILE = "category.conf"


class Category(object):

    __size_change = 1024 * 1024

    def __init__(self, ffEnabled=False):
        self._logger = logging.getLogger(self.__class__.__name__)

        filename = os.path.join(get_lib_path(), 'Core', 'Category', CATEGORY_CONFIG_FILE)
        try:
            self.category_info = getCategoryInfo(filename)
            self.category_info.sort(key=cmp_to_key(cmp_rank))
        except (MissingSectionHeaderError, ParsingError, IOError):
            self.category_info = []
            self._logger.critical('', exc_info=True)

        self.xxx_filter = XXXFilter()

        self._logger.debug("category: Categories defined by user: %s", self.getCategoryNames())

        self.ffEnabled = ffEnabled
        self.set_family_filter(None)

    def getCategoryNames(self, filter=True):
        if self.category_info is None:
            return []
        keys = []
        for category in self.category_info:
            rank = category['rank']
            if rank == -1 and filter:
                break
            keys.append((category['name'], category['displayname']))
        return keys

    def calculateCategory(self, torrent_dict, display_name):
        """
        Calculate the category for a given torrent_dict of a torrent file.
        :return a list of categories this torrent belongs to.
        """
        files_list = []
        try:
            # the multi-files mode
            for ifiles in torrent_dict['info']["files"]:
                files_list.append((ifiles['path'][-1], ifiles['length'] / float(self.__size_change)))
        except KeyError:
            # single mode
            files_list.append(
                (torrent_dict['info']["name"], torrent_dict['info']['length'] / float(self.__size_change)))

        tracker = torrent_dict.get('announce')
        if not tracker:
            announce_list = torrent_dict.get('announce-list', [['']])
            if announce_list and announce_list[0]:
                tracker = announce_list[0][0]

        comment = torrent_dict.get('comment')
        return self.calculateCategoryNonDict(files_list, display_name, tracker, comment)

    def calculateCategoryNonDict(self, files_list, display_name, tracker, comment):
        if self.xxx_filter.isXXXTorrent(files_list, display_name, tracker, comment):
            return 'xxx'

        torrent_category = None
        # filename_list ready
        strongest_cat = 0.0
        for category in self.category_info:  # for each category
            (decision, strength) = self.judge(category, files_list, display_name)
            if decision and (strength > strongest_cat):
                torrent_category = category['name']
                strongest_cat = strength

        if torrent_category is None:
            torrent_category = 'other'

        return torrent_category

    # judge whether a torrent file belongs to a certain category
    # return bool
    def judge(self, category, files_list, display_name=''):

        # judge file keywords
        display_name = display_name.lower()
        factor = 1.0
        fileKeywords = self._getWords(display_name)

        for ikeywords in category['keywords'].keys():
            try:
                fileKeywords.index(ikeywords)
                factor *= 1 - category['keywords'][ikeywords]
            except ValueError:
                pass
        if (1 - factor) > 0.5:
            if 'strength' in category:
                return (True, category['strength'])
            else:
                return (True, (1 - factor))

        # judge each file
        matchSize = 0
        totalSize = 1e-19
        for name, length in files_list:
            totalSize += length
            # judge file size
            if length < category['minfilesize'] or 0 < category['maxfilesize'] < length:
                continue

            # judge file suffix
            OK = False
            for isuffix in category['suffix']:
                if name.lower().endswith(isuffix):
                    OK = True
                    break
            if OK:
                matchSize += length
                continue

            # judge file keywords
            factor = 1.0
            fileKeywords = self._getWords(name.lower())

            for ikeywords in category['keywords'].keys():
                try:
                    fileKeywords.index(ikeywords)
                    # print ikeywords
                    factor *= 1 - category['keywords'][ikeywords]
                except ValueError:
                    pass
            if factor < 0.5:
                matchSize += length

        # match file
        if (matchSize / totalSize) >= category['matchpercentage']:
            if 'strength' in category:
                return True, category['strength']
            else:
                return True, (matchSize / totalSize)

        return False, 0

    WORDS_REGEXP = re.compile('[a-zA-Z0-9]+')

    def _getWords(self, string):
        return self.WORDS_REGEXP.findall(string)

    def family_filter_enabled(self):
        """
        Return is xxx filtering is enabled in this client
        """
        return self.ffEnabled

    def set_family_filter(self, b=None):
        assert b in (True, False, None)
        old = self.family_filter_enabled()
        if b != old or b is None:  # update category data if initial call, or if state changes
            if b is None:
                b = old

            self.ffEnabled = b

            # change category data
            for category in self.category_info:
                if category['name'] == 'xxx':
                    if b:
                        category['old-rank'] = category['rank']
                        category['rank'] = -1
                    elif category['rank'] == -1:
                        category['rank'] = category['old-rank']
                    break

    def get_family_filter_sql(self):
        if self.family_filter_enabled():
            forbiddencats = [cat['name'] for cat in self.category_info if cat['rank'] == -1]
            if forbiddencats:
                return " and category not in (%s)" % ','.join(["'%s'" % cat for cat in forbiddencats])
        return ''


def cmp_rank(a, b):
    if not ('rank' in a):
        return 1
    elif not ('rank' in b):
        return -1
    elif a['rank'] == -1:
        return 1
    elif b['rank'] == -1:
        return -1
    elif a['rank'] == b['rank']:
        return 0
    elif a['rank'] < b['rank']:
        return -1
    else:
        return 1
