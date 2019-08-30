"""
Category.

Author(s):  Yuan Yuan, Jelle Roozenburg
"""
from __future__ import absolute_import, division

import logging
import os
import re
from functools import cmp_to_key

from Tribler.Core.Category.FamilyFilter import default_xxx_filter
from Tribler.Core.Category.init_category import getCategoryInfo
from Tribler.Core.Utilities.install_dir import get_lib_path
from Tribler.Core.Utilities.unicode import recursive_unicode

CATEGORY_CONFIG_FILE = "category.conf"


def cmp_rank(a, b):
    if 'rank' not in a:
        return 1
    if 'rank' not in b:
        return -1
    if a['rank'] == b['rank']:
        return 0
    if a['rank'] == -1:
        return 1
    if b['rank'] == -1:
        return -1
    if a['rank'] < b['rank']:
        return -1
    return 1


class Category(object):
    __size_change = 1024 * 1024
    _logger = logging.getLogger("Category")

    category_info = getCategoryInfo(os.path.join(get_lib_path(), 'Core', 'Category', CATEGORY_CONFIG_FILE))
    category_info.sort(key=cmp_to_key(cmp_rank))

    def calculateCategory(self, torrent_dict, display_name):
        """
        Calculate the category for a given torrent_dict of a torrent file.
        :return a list of categories this torrent belongs to.
        """
        is_xxx = default_xxx_filter.isXXXTorrent(
            files_list=recursive_unicode(torrent_dict[b'info']["files"] if "files" in torrent_dict[b'info'] else []),
            torrent_name=torrent_dict[b'info'].get(b"name", b'').decode('utf-8'),
            tracker=torrent_dict[b'info'].get(b"announce", b'').decode('utf-8'))
        if is_xxx:
            return "xxx"
        files_list = []
        try:
            # the multi-files mode
            for ifiles in torrent_dict[b'info'][b"files"]:
                files_list.append((ifiles[b'path'][-1].decode('utf-8'), ifiles[b'length'] / float(self.__size_change)))
        except KeyError:
            # single mode
            files_list.append(
                (torrent_dict[b'info'][b"name"].decode('utf-8'),
                 torrent_dict[b'info'][b'length'] / float(self.__size_change)))

        tracker = torrent_dict.get(b'announce')
        if not tracker:
            announce_list = torrent_dict.get(b'announce-list', [['']])
            if announce_list and announce_list[0]:
                tracker = announce_list[0][0]

        comment = torrent_dict.get(b'comment')
        return self.calculateCategoryNonDict(files_list, display_name, tracker, comment)

    def calculateCategoryNonDict(self, files_list, display_name, tracker, comment):
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
                return True, category['strength']
            else:
                return True, (1 - factor)

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


# Category filter should be stateless
default_category_filter = Category()
