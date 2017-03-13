# Written by Yuan Yuan
# see LICENSE for license information

# give the initial category information

import ConfigParser


def __split_list(string):
    the_list = []
    for word in string.split(","):
        word = word.strip()
        the_list.append(word)
    return the_list

INIT_FUNC_DICT = {
    "minfilenumber": int,
    "maxfilenumber": int,
    "minfilesize": int,
    "maxfilesize": int,
    "suffix": __split_list,
    "matchpercentage": float,
    "keywords": float,
    "strength": float,
    "displayname": str,
    "rank": int
}


def __get_default():
    category = {}
    category["name"] = ""
    category["keywords"] = {}
    category["suffix"] = []
    category["minfilesize"] = 0
    category["maxfilesize"] = -1
    return category


def getCategoryInfo(filename):
    config = ConfigParser.ConfigParser()
    config.readfp(open(filename))

    cate_list = []
    sections = config.sections()

    for isection in sections:
        category = __get_default()
        category["name"] = isection
        for (name, value) in config.items(isection):
            if name[0] != "*":
                category[name] = INIT_FUNC_DICT[name](value)
            else:
                name = name[1:]
                name = name.strip()
                category["keywords"][name] = INIT_FUNC_DICT["keywords"](value)
        cate_list.append(category)

    return cate_list
