# written by Yuan Yuan, Jelle Roozenburg
# see LICENSE.txt for license information

import os
import re
from Tribler.Category.init_category import getCategoryInfo
from FamilyFilter import XXXFilter

import sys
import logging

from Tribler.__init__ import LIBRARYNAME

category_file = "category.conf"

class Category:

    # Code to make this a singleton
    __single = None
    __size_change = 1024 * 1024

    def __init__(self, install_dir='.', ffEnabled=False):
        self._logger = logging.getLogger(self.__class__.__name__)

        if Category.__single:
            raise RuntimeError("Category is singleton")
        filename = os.path.join(install_dir, LIBRARYNAME, 'Category', category_file)
        Category.__single = self
        try:
            self.category_info = getCategoryInfo(filename)
            self.category_info.sort(rankcmp)
        except:
            self.category_info = []
            self._logger.critical('', exc_info=True)

        self.xxx_filter = XXXFilter(install_dir)

        self._logger.debug("category: Categories defined by user: %s", self.getCategoryNames())

        self.ffEnabled = ffEnabled
        self.set_family_filter(None)

    # return Category instance
    def getInstance(*args, **kw):
        if Category.__single is None:
            Category(*args, **kw)
        return Category.__single
    getInstance = staticmethod(getInstance)

    def delInstance(*args, **kw):
        Category.__single = None
    delInstance = staticmethod(delInstance)

    def getCategoryKeys(self):
        if self.category_info is None:
            return []
        keys = []
        keys.append("All")
        keys.append("other")
        for category in self.category_info:
            keys.append(category['name'])
        keys.sort()
        return keys

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

    def hasActiveCategory(self, torrent):
        try:
            name = torrent['category'][0]
        except:
            self._logger.error('Torrent: %s has no valid category', torrent['content_name'])
            return False
        for category in [{'name': 'other', 'rank': 1}] + self.category_info:
            rank = category['rank']
            if rank == -1:
                break
            if name.lower() == category['name'].lower():
                return True
        # print >> sys.stderr, 'Category: %s was not in %s' % (name.lower(), [a['name'].lower()  for a in self.category_info if a['rank'] != -1])
        return False

    def getCategoryRank(self, cat):
        for category in self.category_info:
            if category['name'] == cat:
                return category['rank']
        return None

    # calculate the category for a given torrent_dict of a torrent file
    # return list
    def calculateCategory(self, torrent_dict, display_name):
        # torrent_dict is the  dict of
        # a torrent file
        # return value: list of category the torrent belongs to

        files_list = []
        try:
            # the multi-files mode
            for ifiles in torrent_dict['info']["files"]:
                files_list.append((ifiles['path'][-1], ifiles['length'] / float(self.__size_change)))
        except KeyError:
            # single mode
            files_list.append((torrent_dict['info']["name"], torrent_dict['info']['length'] / float(self.__size_change)))

        tracker = torrent_dict.get('announce')
        if not tracker:
            tracker = torrent_dict.get('announce-list', [['']])[0][0]

        comment = torrent_dict.get('comment')
        return self.calculateCategoryNonDict(files_list, display_name, tracker, comment)

    def calculateCategoryNonDict(self, files_list, display_name, tracker, comment):
        # Check xxx
        try:

            if self.xxx_filter.isXXXTorrent(files_list, display_name, tracker, comment):
                return ['xxx']
        except:
            self._logger.critical('Category: Exception in explicit terms filter in torrent: %s', display_name, exc_info=True)

        torrent_category = None
        # filename_list ready
        strongest_cat = 0.0
        for category in self.category_info:  # for each category
            (decision, strength) = self.judge(category, files_list, display_name)
            if decision and (strength > strongest_cat):
                torrent_category = [category['name']]
                strongest_cat = strength

        if torrent_category == None:
            torrent_category = ['other']

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
            except:
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
            if (length < category['minfilesize']) or \
                    (category['maxfilesize'] > 0 and length > category['maxfilesize']):
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
#                pass
                try:
                    fileKeywords.index(ikeywords)
                    # print ikeywords
                    factor *= 1 - category['keywords'][ikeywords]
                except:
                    pass
            if factor < 0.5:
                # print filename_list[index] + '#######################'
                matchSize += length

        # match file
        if (matchSize / totalSize) >= category['matchpercentage']:
            if 'strength' in category:
                return (True, category['strength'])
            else:
                return (True, (matchSize / totalSize))

        return (False, 0)

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

    def get_family_filter_sql(self, _getCategoryID, table_name=''):
        if self.family_filter_enabled():
            forbiddencats = [cat['name'] for cat in self.category_info if cat['rank'] == -1]
            if table_name:
                table_name += '.'
            if forbiddencats:
                return " and %scategory_id not in (%s)" % (table_name, ','.join([str(_getCategoryID([cat])) for cat in forbiddencats]))
        return ''


def rankcmp(a, b):
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
