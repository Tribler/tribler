# written by Yuan Yuan, Jelle Roozenburg
# see LICENSE.txt for license information

import os
import re
import logging

from Tribler import LIBRARYNAME
from Tribler.Category.init_category import get_category_info
from Tribler.Category.FamilyFilter import XXXFilter

CATEGORY_CONFIG_FILE = "category.conf"


class Category(object):

    SIZE_CHANGE = 1024 * 1024

    def __init__(self, install_dir='.', ff_enabled=False):
        self._logger = logging.getLogger(self.__class__.__name__)

        filename = os.path.join(install_dir, LIBRARYNAME, 'Category', CATEGORY_CONFIG_FILE)
        try:
            self.category_info = get_category_info(filename)
            self.category_info.sort(cmp_rank)
        except:
            self.category_info = []
            self._logger.critical('', exc_info=True)

        self.xxx_filter = XXXFilter(install_dir)

        self._logger.debug("category: Categories defined by user: %s", self.get_category_names())

        self.ff_enabled = ff_enabled
        self.set_family_filter(None)

    def get_category_names(self, to_filter=True):
        if self.category_info is None:
            return []
        keys = []
        for category in self.category_info:
            rank = category['rank']
            if rank == -1 and to_filter:
                break
            keys.append((category['name'], category['displayname']))
        return keys

    # calculate the category for a given torrent_dict of a torrent file
    # return list
    def calculate_category(self, torrent_dict, display_name):
        # torrent_dict is the  dict of
        # a torrent file
        # return value: list of category the torrent belongs to

        files_list = []
        try:
            # the multi-files mode
            for ifiles in torrent_dict['info']["files"]:
                files_list.append((ifiles['path'][-1], ifiles['length'] / float(Category.SIZE_CHANGE)))
        except KeyError:
            # single mode
            files_list.append((torrent_dict['info']["name"],
                               torrent_dict['info']['length'] / float(Category.SIZE_CHANGE)))

        tracker = torrent_dict.get('announce')
        if not tracker:
            tracker = torrent_dict.get('announce-list', [['']])[0][0]

        comment = torrent_dict.get('comment')
        return self.calculate_category_nondict(files_list, display_name, tracker, comment)

    def calculate_category_nondict(self, files_list, display_name, tracker, comment):
        # Check xxx
        try:

            if self.xxx_filter.is_xxx_torrent(files_list, display_name, tracker, comment):
                return ['xxx']
        except:
            self._logger.critical('Category: Exception in explicit terms filter in torrent: %s',
                                  display_name, exc_info=True)

        torrent_category = None
        # filename_list ready
        strongest_cat = 0.0
        for category in self.category_info:  # for each category
            (decision, strength) = self.judge(category, files_list, display_name)
            if decision and (strength > strongest_cat):
                torrent_category = [category['name']]
                strongest_cat = strength

        if torrent_category is None:
            torrent_category = ['other']

        return torrent_category

    # judge whether a torrent file belongs to a certain category
    # return bool
    def judge(self, category, files_list, display_name=''):
        # judge file keywords
        display_name = display_name.lower()
        factor = 1.0
        file_keywords = self._get_words(display_name)

        for ikeywords in category['keywords'].keys():
            try:
                file_keywords.index(ikeywords)
                factor *= 1 - category['keywords'][ikeywords]
            except:
                pass
        if (1 - factor) > 0.5:
            if 'strength' in category:
                return True, category['strength']
            else:
                return True, (1 - factor)

        # judge each file
        match_size = 0
        total_size = 1e-19
        for name, length in files_list:
            total_size += length
            # judge file size
            if length < category['minfilesize'] or 0 < category['maxfilesize'] < length:
                continue

            # judge file suffix
            is_ok = False
            for isuffix in category['suffix']:
                if name.lower().endswith(isuffix):
                    is_ok = True
                    break
            if is_ok:
                match_size += length
                continue

            # judge file keywords
            factor = 1.0
            file_keywords = self._get_words(name.lower())

            for ikeywords in category['keywords'].keys():
                try:
                    file_keywords.index(ikeywords)
                    # print ikeywords
                    factor *= 1 - category['keywords'][ikeywords]
                except:
                    pass
            if factor < 0.5:
                match_size += length

        # match file
        if (match_size / total_size) >= category['matchpercentage']:
            if 'strength' in category:
                return True, category['strength']
            else:
                return True, (match_size / total_size)

        return False, 0

    WORDS_REGEXP = re.compile('[a-zA-Z0-9]+')

    def _get_words(self, string):
        return self.WORDS_REGEXP.findall(string)

    def family_filter_enabled(self):
        """
        Return is xxx filtering is enabled in this client
        """
        return self.ff_enabled

    def set_family_filter(self, b=None):
        assert b in (True, False, None)
        old = self.family_filter_enabled()
        if b != old or b is None:  # update category data if initial call, or if state changes
            if b is None:
                b = old

            self.ff_enabled = b

            # change category data
            for category in self.category_info:
                if category['name'] == 'xxx':
                    if b:
                        category['old-rank'] = category['rank']
                        category['rank'] = -1
                    elif category['rank'] == -1:
                        category['rank'] = category['old-rank']
                    break

    def get_family_filter_sql(self, get_category_id_func, table_name=''):
        if self.family_filter_enabled():
            forbiddencats = [cat['name'] for cat in self.category_info if cat['rank'] == -1]
            if table_name:
                table_name += '.'
            if forbiddencats:
                return " and %scategory_id not in (%s)" % (table_name,
                                                           ','.join([str(get_category_id_func([cat]))
                                                                     for cat in forbiddencats]))
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
